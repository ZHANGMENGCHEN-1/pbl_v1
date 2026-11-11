"""Session-scoped, immutable Excel uploads and actual two-dimensional K-means."""
import hashlib
import json
import math
import re
from datetime import date, datetime, time
from io import BytesIO
from urllib.parse import unquote
from uuid import uuid4
from zipfile import ZipFile

import numpy as np
from fastapi import APIRouter, Header, HTTPException, Request
from openpyxl import load_workbook
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from starlette.concurrency import run_in_threadpool

from ...shared import store
from ..library.clustering import one_step
from .routes import PROJECT, session_id

router = APIRouter(prefix='/api/projects/teaching-agent/activities/explore_2d', tags=['teaching'])
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 3000
MAX_COLUMNS = 50


def init():
    with store.connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS teaching_datasets(
          id TEXT PRIMARY KEY,project TEXT,session TEXT,filename TEXT,version TEXT,
          raw_file BLOB,data TEXT,created TEXT);
        CREATE INDEX IF NOT EXISTS teaching_datasets_session ON teaching_datasets(project,session);
        CREATE TABLE IF NOT EXISTS teaching_analyses(
          id TEXT PRIMARY KEY,project TEXT,session TEXT,dataset_id TEXT,version TEXT,result TEXT,created TEXT);
        CREATE INDEX IF NOT EXISTS teaching_analyses_session ON teaching_analyses(project,session);
        ''')


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value) and abs(value) <= 1e12


def cell_value(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return str(value)


def parse_excel(raw):
    try:
        with ZipFile(BytesIO(raw)) as archive:
            infos = archive.infolist()
            if len(infos) > 512 or sum(i.file_size for i in infos) > 25 * 1024 * 1024:
                raise HTTPException(413, '表格解压后的内容过大，请删除多余工作表或格式后再上传。')
        workbook = load_workbook(BytesIO(raw), read_only=True, data_only=False, keep_links=False)
        try:
            sheet = workbook.worksheets[0]
            if (sheet.max_column or 0) > MAX_COLUMNS or (sheet.max_row or 0) > MAX_ROWS + 1:
                raise HTTPException(422, '最多支持3000条记录、50列，请先缩小表格范围（也请检查空白区域的格式）。')
            rows = sheet.iter_rows(values_only=True)
            header = list(next(rows, []))
            if len(header) < 2 or any(not isinstance(v, str) or not v.strip() for v in header):
                raise HTTPException(422, '第一行需要填写每列的名称，至少两列，列名不能留空。')
            if len(set(header)) != len(header):
                raise HTTPException(422, '有重复的列名，请给每一列起一个不同的名称。')
            if any(len(name) > 80 for name in header):
                raise HTTPException(422, '列名太长了，每个列名最多80个字。')
            records = []
            for row_number, row in enumerate(rows, 2):
                if row_number > MAX_ROWS + 1 or len(row) > MAX_COLUMNS:
                    raise HTTPException(422, '最多支持3000条记录、50列。')
                values = [cell_value(v) for v in row]
                if any(isinstance(v, str) and len(v) > 2000 for v in values):
                    raise HTTPException(422, f'Excel第{row_number}行的文字过长，每个单元格最多2000字。')
                records.append({'row': row_number, 'values': (values + [None] * len(header))[:len(header)]})
            if not records:
                raise HTTPException(422, '只有列名，没有数据。请在第二行开始填写记录。')
            columns = [{'id': f'c{i}', 'name': name,
                        'numeric_count': sum(numeric(r['values'][i]) for r in records)} for i, name in enumerate(header)]
            defaults = [c['id'] for c in columns if c['numeric_count'] > 0][:2]
            # Never substitute columns after selection; default is explicitly returned and shown.
            return {'sheet': sheet.title, 'columns': columns, 'records': records,
                    'row_count': len(records), 'default_features': defaults,
                    'sheet_count': len(workbook.worksheets)}
        finally:
            workbook.close()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, '无法读取这个.xlsx文件。请确认它是未加密的Excel工作簿，并重新另存为.xlsx。') from exc


def summary(data):
    return {**{k: v for k, v in data.items() if k != 'records'}, 'preview': data['records'][:20]}


def owned_dataset(db, session, id):
    row = db.execute('SELECT data FROM teaching_datasets WHERE id=? AND project=? AND session=?', (id, PROJECT, session)).fetchone()
    if not row:
        raise HTTPException(404, '找不到本次上传的数据，请重新上传。')
    return json.loads(row[0])


def owned_analysis(db, session, id):
    row = db.execute('SELECT result FROM teaching_analyses WHERE id=? AND project=? AND session=?', (id, PROJECT, session)).fetchone()
    if not row:
        raise HTTPException(404, '找不到本次计算结果，请先运行分组。')
    return json.loads(row[0])


def save_upload(raw, filename, session):
    data = parse_excel(raw)
    data.update(id=str(uuid4()), filename=filename, version=hashlib.sha256(raw).hexdigest(), created=store.now())
    with store.connection() as db:
        db.execute('INSERT INTO teaching_datasets VALUES(?,?,?,?,?,?,?,?)',
                   (data['id'], PROJECT, session, filename, data['version'], raw, json.dumps(data, ensure_ascii=False), data['created']))
    return summary(data)


@router.post('/datasets')
async def upload(request: Request, x_session_id: str = Header(default=''), x_file_name: str = Header(default='')):
    session = session_id(x_session_id)
    filename = re.split(r'[/\\]', unquote(x_file_name))[-1]
    if not filename.lower().endswith('.xlsx') or len(filename) > 200:
        raise HTTPException(422, '请选择.xlsx格式的文件，文件名不能超过200个字符。')
    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, '文件超过5MB，请缩小表格后再上传。')
        chunks.extend(chunk)
    if not chunks:
        raise HTTPException(422, '文件是空的，请重新选择。')
    return await run_in_threadpool(save_upload, bytes(chunks), filename, session)


@router.get('/datasets/{id}')
def dataset(id: str, x_session_id: str = Header(default='')):
    with store.connection() as db:
        return summary(owned_dataset(db, session_id(x_session_id), id))


class AnalyzeInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dataset_id: str = Field(min_length=1, max_length=80)
    features: list[str] = Field(min_length=2, max_length=2)


def selected_rows(data, features):
    column_ids = [c['id'] for c in data['columns']]
    if len(set(features)) != 2 or any(f not in column_ids for f in features):
        raise HTTPException(422, '请选择两个不同的列；程序不会自动更换你选择的列。')
    indices = [column_ids.index(f) for f in features]
    valid, excluded = [], []
    for record in data['records']:
        reasons = []
        for index in indices:
            value, name = record['values'][index], data['columns'][index]['name']
            if value is None or value == '':
                reasons.append(f'“{name}”缺失')
            elif not numeric(value):
                reasons.append(f'“{name}”不是可计算数值（文字、公式、日期、布尔值，或数值超出±1万亿）')
        if reasons:
            excluded.append({'row': record['row'], 'reasons': reasons})
        else:
            valid.append({**record, 'coordinates': [record['values'][i] for i in indices]})
    return indices, valid, excluded


@router.post('/preview')
def preview(body: AnalyzeInput, x_session_id: str = Header(default='')):
    with store.connection() as db:
        data = owned_dataset(db, session_id(x_session_id), body.dataset_id)
    _, records, excluded = selected_rows(data, body.features)
    return {'dataset_id': data['id'], 'dataset_version': data['version'], 'features': body.features,
            'total_count': data['row_count'], 'sample_count': len(records), 'excluded': excluded}


@router.post('/analyses')
def analyze(body: AnalyzeInput, x_session_id: str = Header(default='')):
    session = session_id(x_session_id)
    with store.connection() as db:
        data = owned_dataset(db, session, body.dataset_id)
    indices, records, excluded = selected_rows(data, body.features)
    if len(records) < 2:
        raise HTTPException(422, f'所选两列只有{len(records)}条完整的数值记录，至少需要2条。请检查缺失或非数值内容，不会自动换列。')
    x = np.array([r['coordinates'] for r in records], dtype=float)
    unique = np.unique(x, axis=0)
    if len(unique) < 2:
        raise HTTPException(422, '所选两列中的有效数据点都重合，无法分成两组。请选择合适的两列或修改文件。')
    centers = unique[np.random.default_rng(42).choice(len(unique), 2, replace=False)]
    initial_centers = centers.tolist()
    warnings = []
    for iteration in range(1, 101):
        frame = one_step(x, centers)
        centers = np.asarray(frame['centers_after'])
        warnings.extend(frame['warnings'])
        if frame['converged']:
            break
    if not frame['converged']:
        warnings.append('已计算100轮，中心还没有稳定；本图展示最后一轮结果，不能称为已稳定的分组。')
    fields = [data['columns'][i] for i in indices]
    groups = [{'group': i, 'count': frame['labels'].count(i), 'center': centers[i].tolist()} for i in range(2)]
    context = {'activity_id': 'explore_2d', 'source': 'uploaded_excel_real_kmeans',
               'dataset_id': data['id'], 'dataset_version': data['version'], 'filename': data['filename'], 'sheet': data['sheet'],
               'features': fields, 'total_count': data['row_count'], 'sample_count': len(records),
               'excluded_count': len(excluded), 'excluded': excluded, 'groups': groups,
               'ranges': [{'min': float(x[:, i].min()), 'max': float(x[:, i].max())} for i in range(2)],
               'k': 2, 'scaling': 'none', 'distance': 'euclidean', 'seed': 42, 'iterations': iteration,
               'converged': frame['converged'], 'warnings': list(dict.fromkeys(warnings)),
               'interpretation_limits': '分组编号没有好坏之分，中心是所选两列的平均值；分组只说明这两列数值的接近程度，不代表因果或采购结论。'}
    result = {'id': str(uuid4()), 'created': store.now(), **context, 'initial_centers': initial_centers,
              'columns': data['columns'], 'points': [{**r, 'group': frame['labels'][i]} for i, r in enumerate(records)],
              'teaching_context': context}
    with store.connection() as db:
        db.execute('INSERT INTO teaching_analyses VALUES(?,?,?,?,?,?,?)',
                   (result['id'], PROJECT, session, data['id'], data['version'], json.dumps(result, ensure_ascii=False), result['created']))
    return result


@router.get('/analyses/{id}')
def analysis(id: str, x_session_id: str = Header(default='')):
    with store.connection() as db:
        return owned_analysis(db, session_id(x_session_id), id)


class ResultInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    result_id: str = Field(min_length=1, max_length=80)
    counts: list[StrictInt] = Field(min_length=2, max_length=2)
    description: str = Field(min_length=1, max_length=500)


@router.post('/submissions')
def submit(body: ResultInput, x_session_id: str = Header(default='')):
    session = session_id(x_session_id)
    description = body.description.strip()
    if not description:
        raise HTTPException(422, '请用自己的话写一句两组有什么特点。')
    with store.connection() as db:
        result = owned_analysis(db, session, body.result_id)
        if any(n < 0 for n in body.counts) or sum(body.counts) != result['sample_count']:
            raise HTTPException(422, f'两组数量需要是非负整数，合计{result["sample_count"]}条（实际参与计算的记录）。')
        payload = {'kind': 'learning_result', 'student_result': {'counts': body.counts, 'description': description},
                   'tool_result': {'counts': [g['count'] for g in result['groups']], 'centers': [g['center'] for g in result['groups']]},
                   'dataset_id': result['dataset_id'], 'dataset_version': result['dataset_version'], 'features': result['features'],
                   'teaching_context': result['teaching_context']}
        saved = {'id': str(uuid4()), 'result_id': result['id'], 'created': store.now(), 'payload': payload}
        db.execute('INSERT INTO teaching_submissions VALUES(?,?,?,?,?,?,?)',
                   (saved['id'], PROJECT, session, 'explore_2d', result['id'], json.dumps(payload, ensure_ascii=False), saved['created']))
    return saved
