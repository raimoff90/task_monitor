
from typing import Optional, List, Dict, Tuple
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime
import io, csv, json, sqlite3
from . import models

app = FastAPI()
app.mount("/static", StaticFiles(directory="backend/static"), name="static")
env = Environment(loader=FileSystemLoader("backend/templates"), autoescape=select_autoescape(["html","xml"]))

def get_db() -> Session: return models.SessionLocal()
models.Base.metadata.create_all(bind=models.engine)

def ensure_seed(db: Session):
    if db.query(models.Person).count()==0:
        for n in ["Катышкин","Морозов","Намдаков","Траулько","Чистов"]:
            db.add(models.Person(name=n)); db.commit()
    if db.query(models.Task).count()==0:
        t1 = models.Task(title="Пример задачи 1", details="Демонстрация длинного описания для проверки адаптивности и переносов строк в ячейках.", status="in progress", priority=2,
                         dev_color="sky", demo_color="amber", lt_color="emerald", prod_color="rose",
                         dev_status="подготовка", demo_status="демо запланировано", lt_status="тест", prod_status="—")
        t2 = models.Task(title="Пример задачи 2", details="Описание второй задачи", status="new", priority=3,
                         dev_color="emerald", demo_color="sky", lt_color="amber", prod_color="rose",
                         dev_status="идёт разработка", demo_status="", lt_status="", prod_status="")
        db.add_all([t1,t2]); db.commit()
        people = db.query(models.Person).all()
        long_cmt = "Очень длинный комментарий ответственного, который показывает переносы строк, устойчивость окна, отсутствие ограничения по размеру и корректную позицию в правом верхнем углу относительно фамилии пользователя."
        if people:
            db.add(models.Assignment(task_id=t1.id, person_id=people[0].id, stage="DEV", comment=long_cmt))
            db.add(models.Assignment(task_id=t1.id, person_id=people[1].id, stage="DEMO", comment="Готовит презентацию"))
            db.add(models.Assignment(task_id=t2.id, person_id=people[2].id, stage="DEV", comment="Настраивает CI/CD"))
        db.add(models.JiraItem(task_id=t1.id, key="ABC-123", title="Подготовить API", url=""))
        db.add(models.JiraItem(task_id=t1.id, key="ABC-124", title="Сделать демо", url=""))
        db.commit()
    conn = sqlite3.connect("data.db"); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS changes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT NOT NULL,
      kind TEXT NOT NULL,
      payload TEXT NOT NULL
    )""")
    conn.commit(); conn.close()

def log_change(kind: str, payload: dict):
    # richer human-readable text
    txt = None
    try:
        if kind == 'task.save':
            t = payload.get('title') or 'Без названия'
            pr = payload.get('priority_text') or ''
            txt = f"Сохранена задача «{t}» ({pr}). Статусы: DEV='{payload.get('dev_status','')}', DEMO='{payload.get('demo_status','')}', LT='{payload.get('lt_status','')}', PROD='{payload.get('prod_status','')}'."
        elif kind == 'assign.add':
            txt = f"Назначен {payload.get('person')} на {payload.get('stage')} по задаче «{payload.get('title','')}»"
        elif kind == 'assign.remove':
            txt = f"Удалена задача у {payload.get('person')} на {payload.get('stage')} (задача «{payload.get('title','')}»)"
        elif kind == 'assign.update':
            txt = f"Обновлён комментарий у {payload.get('person')} на {payload.get('stage')} (задача «{payload.get('title','')}»): «{payload.get('comment','')}»"
        elif kind == 'task.delete':
            t = payload.get('title') or f"ID {payload.get('task_id')}"
            txt = f"Удалена задача «{t}»"
        elif kind == 'people.create':
            txt = f"Создан ответственный {payload.get('name')}"
        elif kind == 'people.delete':
            n = payload.get('name') or f"ID {payload.get('id')}"
            txt = f"Удалён ответственный {n}"
        elif kind == 'jira.add':
            txt = f"Добавлена Jira-задача {payload.get('key')} к «{payload.get('title','')}»"
        elif kind == 'jira.delete':
            txt = f"Удалена Jira-задача ID {payload.get('item_id')}"
        elif kind == 'tasks.reorder':
            txt = "Обновлён порядок задач на доске"
        else:
            txt = kind
    except Exception:
        txt = kind
    payload = dict(payload or {}); payload['text'] = txt
    conn = sqlite3.connect("data.db"); cur = conn.cursor()
    cur.execute("INSERT INTO changes(ts, kind, payload) VALUES (?,?,?)",
                (datetime.utcnow().isoformat(timespec="seconds")+"Z", kind, json.dumps(payload, ensure_ascii=False)))
    conn.commit(); conn.close()

def render(name: str, **ctx):
    tpl = env.get_template(name)
    return HTMLResponse(tpl.render(**ctx))

@app.get("/", response_class=HTMLResponse)
def index(request: Request, sort: Optional[str]=None, q: Optional[str]=None):
    db = get_db(); ensure_seed(db)
    qry = db.query(models.Task)
    if q:
        like = f"%{q}%"
        from sqlalchemy import or_
        qry = qry.filter(or_(models.Task.title.like(like), models.Task.details.like(like)))
    if sort == "priority_desc": qry = qry.order_by(models.Task.priority.desc(), models.Task.sort_order, models.Task.id)
    elif sort == "priority_asc": qry = qry.order_by(models.Task.priority, models.Task.sort_order, models.Task.id)
    elif sort == "title": qry = qry.order_by(models.Task.title, models.Task.sort_order, models.Task.id)
    else: qry = qry.order_by(models.Task.sort_order, models.Task.id)
    tasks = qry.all()
    people = db.query(models.Person).order_by(models.Person.name).all()
    return render("index.html", request=request, tasks=tasks, people=people, STAGES=models.STAGES, q=q or "", sort=sort or "", tasks_count=len(tasks))

@app.get("/task/new", response_class=HTMLResponse)
def task_new(request: Request):
    db = get_db(); people = db.query(models.Person).order_by(models.Person.name).all()
    tasks_count = db.query(models.Task).count()
    return render("task_edit.html", request=request, task=None, people=people, STAGES=models.STAGES, tasks_count=tasks_count)

@app.get("/task/{tid}", response_class=HTMLResponse)
def task_redirect_edit(request: Request, tid: int):
    return RedirectResponse(url=f"/task/{tid}/edit", status_code=303)

@app.get("/task/{tid}/edit", response_class=HTMLResponse)
def task_edit(request: Request, tid: int):
    db = get_db()
    task = db.get(models.Task, tid)
    if not task: raise HTTPException(404, "Task not found")
    people = db.query(models.Person).order_by(models.Person.name).all()
    tasks_count = db.query(models.Task).count()
    return render("task_edit.html", request=request, task=task, people=people, STAGES=models.STAGES, tasks_count=tasks_count)

def _reorder_for_position(db: Session, task: models.Task, new_index: int):
    tasks: List[models.Task] = db.query(models.Task).order_by(models.Task.sort_order, models.Task.id).all()
    tasks = [t for t in tasks if t.id != task.id]
    new_index = max(0, min(new_index, len(tasks)))
    tasks.insert(new_index, task)
    for idx, t in enumerate(tasks): t.sort_order = idx

@app.post("/task/save")
def task_save(
    task_id: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    details: Optional[str] = Form(""),
    status: Optional[str] = Form("new"),
    priority: Optional[int] = Form(2),
    order_index: Optional[str] = Form(None),
    dev_color: Optional[str] = Form("sky"),
    demo_color: Optional[str] = Form("sky"),
    lt_color: Optional[str] = Form("sky"),
    prod_color: Optional[str] = Form("sky"),
    dev_status: Optional[str] = Form(""),
    demo_status: Optional[str] = Form(""),
    lt_status: Optional[str] = Form(""),
    prod_status: Optional[str] = Form(""),
    assign_json: Optional[str] = Form(""),
    assign_guard: Optional[str] = Form("0"),
    orphan_notes: Optional[str] = Form(""),
):
    db = get_db()
    creating = False
    if task_id:
        try: tid_int = int(task_id)
        except Exception: tid_int = None
        task = db.get(models.Task, tid_int) if tid_int is not None else None
        if not task: raise HTTPException(404, "Task not found")
    else:
        creating = True
        task = models.Task(); task.sort_order = db.query(models.Task).count(); db.add(task)
    # Snapshot previous assignments
    prev: Dict[Tuple[str,int], str] = {}
    if task.id:
        for a in db.query(models.Assignment).filter(models.Assignment.task_id==task.id).all():
            prev[(a.stage, a.person_id)] = a.comment or ""
    # Update fields
    task.title = (title or '').strip() or 'Без названия'
    task.details = (details or '').strip()
    task.status = (status or 'new').strip()
    task.priority = int(priority or 2)
    task.dev_color = dev_color or 'sky'; task.demo_color = demo_color or 'sky'; task.lt_color = lt_color or 'sky'; task.prod_color = prod_color or 'sky'
    task.dev_status = (dev_status or '').strip(); task.demo_status = (demo_status or '').strip(); task.lt_status = (lt_status or '').strip(); task.prod_status = (prod_status or '').strip()
    task.orphan_notes = orphan_notes or ''
    db.commit()
    if order_index not in (None, ""): _reorder_for_position(db, task, int(order_index)); db.commit()
    # Parse new assignments
    newmap: Dict[Tuple[str,int], str] = {}
    if (assign_guard or "0") == "1":
        try:
            items = json.loads(assign_json) if assign_json else []
        except Exception:
            items = []
        for it in items:
            try:
                st = it.get("stage"); pid = int(it.get("person_id")); cmt = it.get("comment","") or ""
                if st and pid:
                    newmap[(st, pid)] = cmt
            except Exception:
                continue
        # Replace assignments only when guard is set
        db.query(models.Assignment).filter(models.Assignment.task_id==task.id).delete()
        for (st, pid), cmt in newmap.items():
            db.add(models.Assignment(task_id=task.id, person_id=pid, stage=st, comment=cmt))
        db.commit()
    else:
        # No JS guard -> keep previous assignments as-is
        newmap = prev.copy()
    # Detailed history
    pr_text = 'высокий' if task.priority==3 else 'средний' if task.priority==2 else 'низкий'
    log_change('task.save', {'task_id': task.id, 'title': task.title, 'priority': task.priority, 'priority_text': pr_text,
                             'dev_status': task.dev_status, 'demo_status': task.demo_status, 'lt_status': task.lt_status, 'prod_status': task.prod_status})
    added = set(newmap.keys()) - set(prev.keys())
    removed = set(prev.keys()) - set(newmap.keys())
    possible_updates = set(prev.keys()) & set(newmap.keys())
    people = {p.id: p.name for p in db.query(models.Person).all()}
    for st, pid in added:
        log_change('assign.add', {'task_id': task.id, 'title': task.title, 'stage': st, 'person': people.get(pid, f'ID {pid}')})
    for st, pid in removed:
        log_change('assign.remove', {'task_id': task.id, 'title': task.title, 'stage': st, 'person': people.get(pid, f'ID {pid}')})
    for st, pid in possible_updates:
        if (prev.get((st,pid),"") != newmap.get((st,pid),"")):
            log_change('assign.update', {'task_id': task.id, 'title': task.title, 'stage': st, 'person': people.get(pid, f'ID {pid}'), 'comment': newmap.get((st,pid),"")})
    return RedirectResponse(url="/", status_code=303)

@app.post("/api/tasks/reorder")
async def api_reorder(request: Request):
    db = get_db(); data = await request.json()
    ids = data.get("ids", [])
    for idx, tid in enumerate(ids):
        t = db.get(models.Task, int(tid))
        if t: t.sort_order = idx
    db.commit(); log_change('tasks.reorder', {'ids': ids}); return {"ok": True}

@app.post("/task/{tid}/delete")
def delete_task(tid: int):
    db = get_db(); t = db.get(models.Task, tid)
    if not t: raise HTTPException(404, "Task not found")
    title = t.title
    db.query(models.Assignment).filter(models.Assignment.task_id==tid).delete()
    db.query(models.JiraItem).filter(models.JiraItem.task_id==tid).delete()
    db.delete(t); db.commit()
    log_change('task.delete', {'task_id': tid, 'title': title})
    return RedirectResponse(url="/", status_code=303)

@app.get("/people", response_class=HTMLResponse)
def people_list(request: Request):
    db = get_db(); people = db.query(models.Person).order_by(models.Person.name).all()
    return render("people.html", request=request, people=people)

@app.post("/people/create")
def people_create(name: str = Form(...)):
    db = get_db(); name = name.strip()
    if not name: raise HTTPException(400, "Empty name")
    if db.query(models.Person).filter(models.Person.name==name).first():
        return RedirectResponse(url="/people", status_code=303)
    db.add(models.Person(name=name)); db.commit()
    log_change('people.create', {'name': name})
    return RedirectResponse(url="/people", status_code=303)

@app.post("/people/{pid}/delete")
def delete_person(pid: int):
    db = get_db(); p = db.get(models.Person, pid)
    if not p: return RedirectResponse(url="/people", status_code=303)
    assigns = db.query(models.Assignment).filter(models.Assignment.person_id==pid).all()
    for a in assigns:
        task = db.get(models.Task, a.task_id)
        line = f"[{a.stage}] {p.name}: {a.comment}\n" if a.comment else f"[{a.stage}] {p.name}\n"
        task.orphan_notes = (task.orphan_notes or "") + line
        db.delete(a)
    pname = p.name
    db.delete(p); db.commit(); log_change('people.delete', {'id': pid, 'name': pname}); return RedirectResponse(url="/people", status_code=303)

@app.get("/task/{tid}/jira", response_class=HTMLResponse)
def jira_page(request: Request, tid: int):
    db = get_db(); task = db.get(models.Task, tid)
    if not task: raise HTTPException(404, "Task not found")
    items = db.query(models.JiraItem).filter(models.JiraItem.task_id==tid).order_by(models.JiraItem.id).all()
    return render("task_jira.html", request=request, task=task, items=items)

@app.post("/task/{tid}/jira/add")
def jira_add(tid: int, key: str = Form(...), title: str = Form(""), url: str = Form("")):
    db = get_db(); task = db.get(models.Task, tid)
    if not task: raise HTTPException(404, "Task not found")
    db.add(models.JiraItem(task_id=tid, key=key.strip(), title=title.strip(), url=url.strip())); db.commit()
    log_change('jira.add', {'task_id': tid, 'title': task.title, 'key': key})
    return RedirectResponse(url=f"/task/{tid}/jira", status_code=303)

@app.post("/task/{tid}/jira/delete/{jid}")
def jira_delete(tid: int, jid: int):
    db = get_db(); it = db.get(models.JiraItem, jid)
    if it and it.task_id==tid: db.delete(it); db.commit()
    log_change('jira.delete', {'task_id': tid, 'item_id': jid})
    return RedirectResponse(url=f"/task/{tid}/jira", status_code=303)

@app.get("/history", response_class=HTMLResponse)
def history(request: Request):
    conn = sqlite3.connect('data.db'); cur = conn.cursor()
    rows = cur.execute('SELECT ts, kind, payload FROM changes ORDER BY id DESC LIMIT 500').fetchall()
    items = []
    for r in rows:
        try:
            pl = json.loads(r[2]); text = pl.get('text')
        except Exception:
            pl = {}; text = None
        items.append({'ts': r[0], 'kind': r[1], 'text': text or r[1], 'payload': pl})
    conn.close()
    return render("history.html", request=request, items=items)

@app.get("/export/csv")
def export_csv():
    db = get_db(); tasks = db.query(models.Task).order_by(models.Task.sort_order, models.Task.id).all()
    output = io.StringIO(newline=''); output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["id","title","status","priority","dev_status","demo_status","lt_status","prod_status","dev_color","demo_color","lt_color","prod_color"])
    for t in tasks:
        writer.writerow([t.id, t.title, t.status, t.priority, t.dev_status, t.demo_status, t.lt_status, t.prod_status, t.dev_color, t.demo_color, t.lt_color, t.prod_color])
    output.seek(0)
    return StreamingResponse(iter([output.read()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=tasks.csv"})
