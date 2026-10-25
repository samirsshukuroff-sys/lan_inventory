from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
import ipaddress
import os
# Импортируем наши рабочие функции из inventory.py
from .inventory import scan_network, generate_excel

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

SCAN_RESULTS_FILE = "inventory_result.xlsx"

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse(request, "index.html", {"request": request})

@app.post("/scan")
async def start_scan(
    request: Request,
    network: str = Form(...),
    scan_mode: str = Form(...),
    domain: str = Form("asco.az"),
    domain_user: str = Form(""),
    domain_pass: str = Form(""),
    local_user: str = Form(""),
    local_pass: str = Form(""),
    delay: float = Form(1.5)
):
    try:
        net = ipaddress.ip_network(network, strict=False)
        ip_list = [str(ip) for ip in net.hosts()]
    except ValueError:
        return templates.TemplateResponse(request, "index.html", {"request": request, "error": "Неверный формат подсети!"})

    # Вызываем НАШУ новую функцию сканирования
    results = scan_network(
        ip_list=ip_list,
        domain=domain,
        domain_user=domain_user,
        domain_pass=domain_pass,
        local_user=local_user,
        local_pass=local_pass,
        scan_mode=scan_mode,
        delay_sec=delay
    )

    generate_excel(results, SCAN_RESULTS_FILE)

    return templates.TemplateResponse(request, "index.html", {
        "request": request,
        "success": True,
        "count": len(results),
        "download_ready": True
    })

@app.get("/download")
def download_file():
    if os.path.exists(SCAN_RESULTS_FILE):
        return FileResponse(path=SCAN_RESULTS_FILE, filename="LAN_Inventory_ASCO.xlsx")
    return {"error": "Файл еще не создан"}
