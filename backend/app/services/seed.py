from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.models import Candidate, Hall, PaperSet

def seed_if_empty(db: Session) -> None:
    if (db.scalar(select(func.count()).select_from(Hall)) or 0) > 0:
        return
    # 4x5=20 格，最小曼哈顿距离 2 时棋盘格有效容量仅 10；12 名考生制造格位紧张。
    hall = Hall(code="H101", name="一号考室", rows=4, cols=5, min_manhattan=2)
    db.add(hall); db.flush()
    papers = [("P-A", "语文 A 卷"), ("P-B", "语文 B 卷"), ("P-C", "语文 C 卷")]
    paper_ids = []
    for code, title in papers:
        p = PaperSet(code=code, title=title)
        db.add(p); db.flush()
        paper_ids.append(p.id)
    names = ["陈一", "李二", "张三", "赵四", "钱五", "孙六", "周七", "吴八", "郑九", "王十", "冯十一", "陈十二"]
    for i, name in enumerate(names):
        # 恰一名关键考生：只要该标记存在，提交排座时场次即封闭、必须全员落座。
        db.add(Candidate(hall_id=hall.id, name=name, ticket_no=f"T{2026001+i}",
                         paper_id=paper_ids[i % len(paper_ids)], is_key=(i == 0)))
    db.commit()
