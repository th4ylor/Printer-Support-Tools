from __future__ import annotations
from ..config import CONFIG
from ..logger import build_logger
from ..models import Resultado_Operacao
from .diagnostic import DiagnosticsService
from .printer_service import PrinterService
from .spooler_service import SpoolerService

class Auto_fix:
    def __init__(self):
        self.logger = build_logger("Serviço_AutoFix")
        self.printer_service = PrinterService()
        self.spooler_service = SpoolerService()
        self.diagnostic_service = DiagnosticsService()
        
    def one_click_fix(self, printer_name, ip_or_host, driver_name):
        return self.click_fix(printer_name, ip_or_host, driver_name)

    def click_fix(self, printer_name, ip_or_host, driver_name):
        anotacoes = []
        for tentativa in range(1, CONFIG.max_retry + 1):
            self.logger.info("Tentativa de correção automatica %s para %s", tentativa, printer_name)
            diag = self.diagnostic_service.run_diagnostic(printer_name, ip_or_host)
            if diag.printer_online:
                return Resultado_Operacao(True, "Nenhuma correção necessária, impressora já está online.", {"Notas": anotacoes})
            
            if not diag.spooler_rodando:
                sp = self.spooler_service.Resetar_spooler()
                anotacoes.append(sp.message)
                
            if not diag.porta_9100_ok or not diag.ping_ok:
                remover = self.printer_service.remover_impressora(printer_name)
                anotacoes.append(remover.message)
                reinstalar = self.printer_service.reinstalar_impressora(
                    printer_name=printer_name,
                    ip_ou_hostname=ip_or_host,
                    driver_name=driver_name,
                )
                anotacoes.append(reinstalar.message)
                
            post = self.diagnostic_service.run_diagnostic(printer_name, ip_or_host)
            if post.printer_online:
                return Resultado_Operacao(True, "Correção automática concluida com sucesso.", {"Tentativas": tentativa, "anotacoes":anotacoes},)
            
        return Resultado_Operacao(False, "A correção automática não conseguiu restaurar a impressora. Por favor, contate a equipe de TI.", {"Anotações": anotacoes})    