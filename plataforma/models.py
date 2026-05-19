from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class PrinterInfo:
    name: str
    driver_name: str
    port_name: str
    is_default: bool = False
    status: str = "Unknown"
    location: str = ""
    comentario: str = ""

@dataclass
class Resultado_Operacao:
    success: bool
    message: str
    details: dict[str, Any] | None = None
    marcacao_hora: datetime = field(default_factory = datetime.now)

@dataclass
class DiagosticReport:
    nome_impressora: str
    ip: str
    ping_ok: bool
    porta_9100_ok: bool
    spooler_rodando: bool
    printer_online: bool
    anotacoes: list[str] = field(default_factory=list)