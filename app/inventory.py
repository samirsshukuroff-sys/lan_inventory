import socket
import time
import os
import openpyxl
import winrm
import json

def ping_host(host):
    response = os.system(f"ping -c 1 -w 1 {host} > /dev/null 2>&1")
    return response == 0

def get_wmi_data(ip, user, password, domain=""):
    try:
        if domain and domain != ".":
            user = f"{domain}\\{user}"
        session = winrm.Session(f'http://{ip}:5985/wsman', auth=(user, password), transport='ntlm')
        ps_script = """
        $os = Get-CimInstance Win32_OperatingSystem
        $cpu = Get-CimInstance Win32_Processor
        $ram = [math]::round($os.TotalVisibleMemorySize / 1MB, 2)
        $disk = Get-CimInstance Win32_DiskDrive | Select-Object -First 1
        $mac = Get-CimInstance Win32_NetworkAdapterConfiguration | Where-Object { $_.IPEnabled -eq $true } | Select-Object -First 1 -ExpandProperty MACAddress
        [PSCustomObject]@{
            Hostname = $os.CSName
            CPU = $cpu.Name
            RAM = "$ram GB"
            Disk = "$($disk.MediaType) $([math]::round($disk.Size / 1GB, 2)) GB"
            MAC = $mac
        } | ConvertTo-Json
        """
        result = session.run_ps(ps_script)
        if result.status_code == 0:
            data = json.loads(result.std_out.decode('utf-8').strip())
            return {
                "hostname": data.get("Hostname", "Unknown"),
                "cpu": data.get("CPU", "Unknown"),
                "ram_gb": data.get("RAM", "Unknown"),
                "disk_type_size": data.get("Disk", "Unknown"),
                "mac": data.get("MAC", "Unknown")
            }
        else:
            raise Exception("WinRM вернул ошибку")
    except Exception as e:
        raise Exception(f"WinRM Error: {e}")

def scan_network(ip_list, domain, domain_user, domain_pass, local_user, local_pass, scan_mode, delay_sec=1.5):
    results = []
    print(f"[*] СТАРТ СКАНИРОВАНИЯ. Всего IP: {len(ip_list)}", flush=True)

    for ip in ip_list:
        if not ping_host(ip):
            continue

        print(f"[+] Хост {ip} онлайн. Пробуем WinRM...", flush=True)
        time.sleep(delay_sec)

        credentials = []
        if scan_mode in ['domain', 'both'] and domain_user and domain_pass:
            credentials.append((domain, domain_user, domain_pass, "Domain"))
        if scan_mode in ['local', 'both'] and local_user and local_pass:
            credentials.append(('.', local_user, local_pass, "Local"))

        success = False
        for dom, user, password, auth_type in credentials:
            try:
                hw = get_wmi_data(ip, user, password, dom)
                results.append({
                    "ip": ip, "hostname": hw["hostname"], "cpu": hw["cpu"], 
                    "ram_gb": hw["ram_gb"], "disk_type_size": hw["disk_type_size"], 
                    "mac": hw["mac"], "auth_used": auth_type, "status": "OK"
                })
                print(f"    [✔] РЕАЛЬНЫЙ УСПЕХ: {hw['hostname']} опрошен по WinRM!", flush=True)
                success = True
                break 
            except Exception as e:
                print(f"    [X] Ошибка к {ip}: {e}", flush=True)

        if not success:
            results.append({
                "ip": ip, "hostname": "Unknown", "cpu": "Access Denied", 
                "ram_gb": "-", "disk_type_size": "-", "mac": "-", 
                "auth_used": "Failed", "status": "Error"
            })

    print(f"[*] СКАНИРОВАНИЕ ЗАВЕРШЕНО. Найдено: {len(results)}", flush=True)
    return results

def generate_excel(data_list, filename="inventory.xlsx"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventory"
    headers = ["IP Address", "PC Name", "Processor", "RAM", "HDD/SSD", "MAC Address", "Auth Type"]
    ws.append(headers)
    for item in data_list:
        ws.append([item.get("ip"), item.get("hostname"), item.get("cpu"), item.get("ram_gb"), item.get("disk_type_size"), item.get("mac"), item.get("auth_used")])
    wb.save(filename)
    return filename
