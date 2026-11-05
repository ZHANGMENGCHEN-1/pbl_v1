"""Create packaged workbooks once. Never overwrite teacher-provided workbooks."""
from pathlib import Path
from openpyxl import Workbook

root = Path(__file__).resolve().parents[1] / "datasets" / "library"
root.mkdir(exist_ok=True)
books = [("B1", "种梨", 2, 30), ("B2", "傲慢与偏见", 6, 2), ("B3", "如果历史是一群猫", 9, 17), ("B4", "浙江寻宝记", 16, 14), ("B5", "奇妙博物院", 18, 28)]
datasets = {
    "library_sample_1d.xlsx": [["id", "name", "borrow_count"], *[[i, n, c] for i, n, c, d in books]],
    "library_sample_2d.xlsx": [["id", "name", "borrow_count", "borrow_days"], *[list(b) for b in books]],
    "reading_interest_demo.xlsx": [["id", "name", "content_preference", "duration_preference"], *[[f"D{i+1:02}", f"演示样本{i+1:02}", max(0, min(100, c + (i % 5 - 2) * 4)), max(0, min(100, d + (i % 3 - 1) * 7))] for i in range(30) for c, d in [(20, 25) if i < 12 else (80, 35) if i < 22 else (65, 80)]]],
}
for name, rows in datasets.items():
    path = root / name
    if path.exists():
        continue
    book = Workbook()
    for row in rows:
        book.active.append(row)
    book.save(path)
    print("Created", name)
