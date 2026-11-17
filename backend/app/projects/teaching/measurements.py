"""Stable survey numbering and additive migration for existing rating records."""

QUESTIONNAIRE_VERSION = 'learning-state-v3'
ACTIVITY_NUMBERS = {'group_books': 1, 'explain_algorithm': 2, 'explore_2d': 3}
SEQUENCES = {
    'student_survey_no': ('project', 'source_route', 'class_name', 'student_number'),
    'session_survey_no': ('project', 'session'),
    'activity_survey_no': ('project', 'session', 'activity'),
}


def next_numbers(db, record):
    numbers = {}
    for column, fields in SEQUENCES.items():
        where = ' AND '.join(f'{field}=?' for field in fields)
        numbers[column] = db.execute(f'SELECT COALESCE(MAX({column}),0)+1 FROM teaching_state_measurements WHERE {where}', tuple(record[field] for field in fields)).fetchone()[0]
    return numbers


def init(db):
    columns = {row['name'] for row in db.execute('PRAGMA table_info(teaching_state_measurements)')}
    additions = {
        'student_survey_no': 'INTEGER', 'session_survey_no': 'INTEGER', 'activity_survey_no': 'INTEGER',
        'activity_number': 'INTEGER', 'survey_phase': 'TEXT', 'questionnaire_version': 'TEXT',
        'response_mode': 'TEXT', 'started_at': 'TEXT', 'response_duration_ms': 'INTEGER',
    }
    for name, kind in additions.items():
        if name not in columns:
            db.execute(f'ALTER TABLE teaching_state_measurements ADD COLUMN {name} {kind}')
    # First migration assigns old records in saved timestamp/ID order. Later runs
    # append missing numbers after the existing maximum; never renumber records.
    rows = db.execute('SELECT * FROM teaching_state_measurements WHERE student_survey_no IS NULL OR session_survey_no IS NULL OR activity_survey_no IS NULL ORDER BY created,id').fetchall()
    for row in rows:
        numbers = next_numbers(db, row)
        db.execute('UPDATE teaching_state_measurements SET student_survey_no=COALESCE(student_survey_no,?),session_survey_no=COALESCE(session_survey_no,?),activity_survey_no=COALESCE(activity_survey_no,?) WHERE id=?', (numbers['student_survey_no'], numbers['session_survey_no'], numbers['activity_survey_no'], row['id']))
    for activity, number in ACTIVITY_NUMBERS.items():
        db.execute('UPDATE teaching_state_measurements SET activity_number=? WHERE activity=? AND activity_number IS NULL', (number, activity))
    db.execute("UPDATE teaching_state_measurements SET survey_phase=COALESCE(survey_phase,'post_activity'),questionnaire_version=COALESCE(questionnaire_version,'legacy-unspecified'),response_mode=COALESCE(response_mode,'legacy-unspecified')")
    for column, fields in SEQUENCES.items():
        db.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS teaching_measurements_{column} ON teaching_state_measurements({",".join(fields)},{column})')
    db.execute('''CREATE VIEW IF NOT EXISTS teaching_state_measurement_records AS
        SELECT id,project,class_name,student_number,source_route,session,
               student_survey_no,session_survey_no,activity_survey_no,activity,activity_number,
               survey_phase,submission_id,questionnaire_version,response_mode,
               json_extract(ratings,'$.difficulty') AS difficulty,
               json_extract(ratings,'$.boredom') AS boredom,
               json_extract(ratings,'$.frustration') AS frustration,
               json_extract(ratings,'$.self_efficacy') AS self_efficacy,
               started_at,created AS submitted_at,response_duration_ms,request_id
        FROM teaching_state_measurements''')


def response(row):
    import json
    return {'id': row['id'], 'created': row['created'], 'activity_id': row['activity'],
            'submission_id': row['submission_id'], 'ratings': json.loads(row['ratings']),
            **{key: row[key] for key in ('student_survey_no', 'session_survey_no', 'activity_survey_no', 'activity_number', 'survey_phase', 'questionnaire_version', 'response_mode', 'started_at', 'response_duration_ms')}}
