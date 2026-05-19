from __future__ import annotations
import json
import subprocess
import time
from pathlib import Path
import win32print

from ..config import CONFIG
from ..models import Resultado_Operacao, PrinterInfo
from ..utilitarios.network import ping_host, traduzir_hostname
from .spooler_service import SpoolerService
from ..logger import build_logger

class PrinterService:
    def __init__(self):
        self.logger = build_logger("printer_service")
        self.spooler = SpoolerService()
        CONFIG.backup_dir.mkdir(parents = True, exist_ok = True)

    def printers_instaladas(self):
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        impressoras = win32print.EnumPrinters(flags, None, 2)
        try:
            impressora_padrao = win32print.GetDefaultPrinter()
        except Exception:
            impressora_padrao = ""
        items = []
        for entry in impressoras:
            if isinstance(entry, dict):
                name = entry.get("pPrinterName", "") or ""
                comment = entry.get("pComment", "") or ""
                driver_name = entry.get("pDriverName", "") or ""
                port_name = entry.get("pPortName", "") or ""
                status = str(entry.get ("pStatus", "Unknown"))
                location = entry.get("pLocation", "") or ""
                if not name:
                    continue
                items.append(
                    PrinterInfo(
                        name = name,
                        driver_name = driver_name,
                        port_name = port_name,
                        is_default = name == impressora_padrao,
                        status = status,
                        location = location,
                        comentario  = comment,
                    )
                )
                continue
            # Compatibilidade com formatos em tupla
            if isinstance(entry, tuple) and len(entry) >= 3:
                name = str(entry[2] or "")
                comment = str(entry[3] or "") if len(entry) > 3 else ""
            else:
                continue

            try:
                handle = win32print.OpenPrinter(name)
                info = win32print.GetPrinter(handle, 2)
                win32print.ClosePrinter(handle)

                items.append(
                    PrinterInfo(
                        name=name,
                        driver_name=info.get("pDriverName", "") or "",
                        port_name=info.get("pPortName", "") or "",
                        is_default=name == impressora_padrao,
                        status=str(info.get("Status", "Desconhecido")),
                        location=info.get("pLocation", "") or "",
                        comentario=comment or "",
                    )
                )
            except Exception:
                self.logger.exception("Falha ao ler detalhes da impressora: %s", name)
        return sorted(items, key = lambda p: p.name.lower())
    
    def detectar_HP(self):
        return[
            p
            for p in self.printers_instaladas()
            if "hp" in p.name.lower()
            or CONFIG.Modelo.lower() in p.driver_name.lower()
        ]
    def backup_config(self,printer_name):
        try:
            impressoras = self.printers_instaladas()
            match = next((p for p in impressoras if p.name == printer_name), None)
            if not match:
                return Resultado_Operacao(False, "Impressora não encontrada para backup" )
            backup_file = CONFIG.backup_dir / f"{printer_name.replace(' ', '_')}.json"
            backup_file.write_text(json.dumps(match.__dict__ , indent= 2), encoding= "utf-8")
            return Resultado_Operacao(True, "Backup da impressora Criado.", {"patch": str(backup_file)})
        except Exception as erro:
            self.logger.exception("Falha no Backup.")
            return Resultado_Operacao(False, f"Falha no Backup: {erro}")
        
    def remover_impressora(self, printer_name):
        impressoras = self.printers_instaladas()
        alvo = next((p for p in impressoras if p.name.lower() == printer_name.lower()), None)
        if not alvo:
            return Resultado_Operacao(False, "A impressora selecionada não existe")
        self.logger.info("Removing printer fully: %s", printer_name)
        backup = self.backup_config(printer_name)
        detalhes: dict = {"backup": backup.message}
        fila_limpeza = self._clear_jobs_for_printer(alvo.name)
        detalhes["queue"] = fila_limpeza.message        
        
# Remocao nativa com PowerShell (Melhor pra filas locais de rede)
        ps_remove = (
            "$n = '{name}'; "
            "$p = Get-Printer -Name $n -ErrorAction SilentlyContinue; "
            "if ($null -ne $p) {{Remove-Printer -Name $n -ErrorAction SilentlyContinue }}"
        ).format(name=alvo.name.replace("'", "''"))
        remove_full = self._run_powershell(ps_remove, timeout = 40)
        detalhes["remove_printer_ss"] = (
            "ok"
            if remove_full.returncode == 0
            else f"rc={remove_full.returncode} err={remove_full.stderr.strip()}"
        )
        
        
        
        
#Alternativa para impressoras como servidor etc
        try:
            win32print.DeletePrinterConnection(alvo.name)
            detalhes["remove_connection"] = "Conexão removida ou não aplicada"
        except Exception as exc:
            detalhes["remove_connection"] = f"Remoção de conexão ignorada: {exc}"
            
#Recurso de fallback pra exclusão de identificadores de fila local
        try:
            handle = win32print.OpenPrinter(alvo.name)
            win32print.DeletePrinter(handle)
            win32print.ClosePrinter(handle)
            detalhes["remove_printer_win32"] = "Impressora removida via win32"
        except Exception as exc:
            self.logger.warning("Win32 removal fallback failed: %s", exc)
            detalhes["remove_printer_win32"] = f"win32 fallback issue: {exc}"

#Ultima tentativa usando PrintUI
        completed = subprocess.run(
            ["rundll32", "printui.dll,PrintUIEntry", "/dl", "/n", alvo.name],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        detalhes["remove_printer_printui"] = (
            "ok"
            if completed.returncode == 0
            else f"rc={completed.returncode} err ={completed.stderr.strip()}"
        )
        self.spooler.Resetar_spooler()
        time.sleep(3)
        
        if alvo.port_name and not self._is_port_in_use_by_other_printers(alvo.port_name, alvo.name):
            self._deletar_porta(alvo.port_name)
            detalhes["port"] = f"Porta {alvo.port_name} checked."
        elif alvo.port_name:
            detalhes["port"] = f"Porta {alvo.port_name} está em uso por outra impressora"
                    
        if alvo.driver_name and not self._is_driver_in_use_by_other_printers(alvo.driver_name, alvo.name):
            self._deletar_driver(alvo.driver_name)
            detalhes["driver"] = f"Driver {alvo.driver_name} checked."
        elif alvo.driver_name:
            detalhes["driver"] = f"Driver {alvo.driver_name} está em uso por outra impressora."     
        ainda_existe =any(p.name.lower() == alvo.name.lower() for p in self.printers_instaladas())
        success = not ainda_existe
        mensagem = "Impressora removida com sucesso." if success else "Impressora ainda presente."
        return Resultado_Operacao(success, mensagem, details=detalhes )
        
    def reinstalar_impressora(
        self,
        printer_name: str,
        ip_ou_hostname: str,
        driver_name: str,
        port_name: str | None = None,
        ):
        host = ip_ou_hostname.strip()
        resolvido = traduzir_hostname(host) if not host.replace(".", "").isdigit() else host
        if not resolvido:
            return Resultado_Operacao(False, "Falha na resolução de hostname")
        if not ping_host(resolvido, CONFIG.ping_timeout_ms):
            return Resultado_Operacao(False, "A impressora não está respondendo ao ping")
            
        porta_escolhida = port_name or f"IP_{resolvido}"
        resultado_porta = self._create_tcp_port(porta_escolhida, resolvido)
        if not resultado_porta.success:
            return resultado_porta
            
        possivel_driver = self._possivel_driver_resolvido(driver_name)
        tentativa_instalacao = []
        
        for candidato in possivel_driver:
            add_result = self._add_printer_powershell(printer_name, porta_escolhida, candidato)
            tentativa_instalacao.append(
                {
                    "driver": candidato,
                    "mathod": "add_Printer",
                    "returncode": str(add_result.returncode),
                    "stderr": add_result.stderr.strip(),
                }
            )
            if add_result.returncode == 0 and self._wait_printer_created(printer_name):
                return Resultado_Operacao(
                    True,  
                    "Impressora Instalada com secesso",
                    details = {"Driver usado": candidato, "Port": porta_escolhida}
                )
                
            printui_result = self._add_printer_printui(printer_name, porta_escolhida, candidato)
            tentativa_instalacao.append(
                {
                    "driver": candidato,
                    "method": "PrintUI",
                    "returncode": str(printui_result.returncode),
                    "stderr": printui_result.stderr.strip(),
                }
            )
            if printui_result.returncode == 0 and self._wait_printer_created(printer_name):
                return Resultado_Operacao(
                    True,  
                    "Impressora Instalada com secesso",
                    details = {"Driver usado": candidato, "Port": porta_escolhida},
                )
                
        drivers_instalados = self._lista_nome_drivers()
        return Resultado_Operacao(
            False,
            "falha na reinstalação: driver não encontrado/compativel neste computador.",
            details = {
                "driver_necessario": driver_name,
                "candidate_drivers": candidato,
                "tentativas": tentativa_instalacao,
                "contagem_drivers_instalado": len(drivers_instalados),
                "exemplo_drivers_instalads": drivers_instalados[:10],
                "dica": "Instale o driver HP correto no Windows e tente novamente.",
            },
                
        )
        
    def _wait_printer_created(self, printer_name, retries = 6, delay_s = 2.0 ):
        for _ in range(retries):
            time.sleep(delay_s)
            if any(p.name.lower() == printer_name.lower() for p in self.printers_instaladas()):
                return True
        return False
    
    def _add_printer_powershell(self, printer_name, port_name, driver_name):
        ps_script = (
            "$name = '{name}'; $port = '{port}'; $driver = '{driver}'; "
            "$existing = Get-Printer -Name $name -ErrorAction SilentlyContinue; "
            "if ($null -ne $existing) {{ Remove-Printer -Name $name -ErrorAction SilentlyContinue }}; "
            "Add-Printer -Name $name -PortName $port -DriverName $driver -ErrorAction Stop"
        ).format(
            name = printer_name.replace("'", "''"),
            port = port_name.replace("'", "''"),
            driver = driver_name.replace("'", "''"),
        )
        return self._run_powershell(ps_script, timeout = 90)

    def _add_printer_printui(self, printer_name, port_name, driver_name):
        args = [
            "rundll32",
            "printui.dll,PrintUIEntry",
            "/if",
            "/b",
            printer_name,
            "/r",
            port_name,
            "/m",
            driver_name,
            "/z",
        ]
        self.logger.info("Reinstall command: %s", " ".join(args))
        return subprocess.run(args, capture_output=True, text=True, check=False, timeout=90)
    
    def _lista_nome_drivers(self):
        ps_script = (
            "Get-PrinterDriver | Select-Object -ExpandProperty Name | "
            "Sort-Object -Unique | ForEach-Object { $_ }"
        )
        completado = self._run_powershell(ps_script, timeout = 30)
        if completado.returncode != 0:
            self.logger.warning("Não foi possivel listar os drivers da impressora: %s", completado.stderr.strip())
            return []
        return [line.strip() for line in completado.stdout.splitlines() if line.strip()]
    
    def _possivel_driver_resolvido(self, driver_solicitado):
        instalado = self._lista_nome_drivers()
        if not instalado:
            return [driver_solicitado]
        
        solicitado_antes = driver_solicitado.lower().strip()
        exato = [d for d in instalado if d.lower() == solicitado_antes]
        if exato:
            return exato
        
    # Priorizar os nomes semelhantes ao HP/M428 caso nao achar o nome exato
        contidos = [ d for d in instalado if solicitado_antes in d.lower()]
        hp_relacionada = [
            d for d in instalado
            if "hp" in d.lower() or "laserjet" in d.lower() or "m428" in d.lower()
        ]

        candidatos = []
        candidatos.extend(contidos)
        candidatos.extend([d for d in hp_relacionada if d not in candidatos])
        
        if driver_solicitado not in candidatos:
            candidatos.insert(0, driver_solicitado)
        return candidatos[:8]
    
    def _create_tcp_port(self, port_name, host):
        ps_script = (
            "if (-not (Get-PrinterPort -Name '{p}' -ErrorAction SilentlyContinue)) "
            "{{Add-PrinterPort -Name '{p}' -PrinterHostAddress '{h}'}}"
        ).format(p = port_name, h = host)
        completado = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            check= False,
            timeout=30,
        )
        if completado.returncode != 0:
            self.logger.error("Falha na criação da porta: %s", completado.stderr.strip())
            return Resultado_Operacao(False, "Falha ao criar a porta TCP/IP.", { "stderr": completado.stderr})
        return Resultado_Operacao(True, f"Porta pronta: {port_name}" )
    
    def _deletar_porta(self, port_name):
        ps_script = f"Remove-PrinterPort -Name '{port_name}' -ErrorAction SilentlyContinue"
        self._run_powershell(ps_script, timeout = 25)
        
    def _deletar_driver(self, driver_name):
        ps_script = f"Remove-PrinterDriver -Name '{driver_name}' -ErrorAction SilentlyContinue"
        self._run_powershell(ps_script, timeout = 25)
        
    def _run_powershell(self, script, timeout = 30):
        return subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output= True,
            text= True,
            check= False,
            timeout= timeout,
        )
        
    def _is_driver_in_use_by_other_printers(self, driver_name, remover_nome_printer):
        for printer in self.printers_instaladas():
            if printer.name.lower() == remover_nome_printer.lower():
                continue
            if printer.driver_name.lower() == driver_name.lower():
                return True
        return False
    
    def _is_port_in_use_by_other_printers(self, port_name, remover_nome_printer):
        for printer in self.printers_instaladas():
            if printer.name.lower() == remover_nome_printer.lower():
                continue
            if printer.port_name.lower() == port_name.lower():
                return True
        return False
    
    def  _clear_jobs_for_printer(self, printer_name):
        try:
            handle = win32print.OpenPrinter(printer_name)
            jobs = win32print.EnumJobs(handle, 0, -1, 1)
            for job in jobs:
                win32print.SetJob(handle, job["JobId"], 0, None, win32print.JOB_CONTROL_DELETE)
            win32print.ClosePrinter(handle)
            return Resultado_Operacao(True, f"{len(jobs)} trabalhos da fila removidos.")
        except Exception as exc:
            return Resultado_Operacao(False, f"Falha na limpeza da fila: {exc}")
        