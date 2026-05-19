from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class AppConfig:
    app_name = "Printer Support - Casa Nova Locadora"
    pasta_impressora = r"C:\Windows\System32\spool\PRINTERS"
    ping_timeout_ms = 1200
    timeout_port9100 = 2.0
    max_retry = 3
    operation_timeout_s = 60
    Modelo = "HP LaserJet"
    hostname_printer_padrao = "HP LaserJet Pro M428f-M429f"

    @property
    def default_printer_hostname(self):
        return self.hostname_printer_padrao
    log_dir_name = "logs"
    backup_dir_name = "backups"

    @property
    def pasta_root(self):
        return Path (__file__).resolve().parent.parent
    
    @property
    def backup_dir(self):
        return self.pasta_root / self.backup_dir_name

    @property
    def log_dir(self):
        return self.pasta_root / self.log_dir_name
    
    
CONFIG = AppConfig()