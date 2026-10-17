# Printer Support Tools

Aplicativo em Python com interface gráfica para dar manutenção rápida em problemas comuns de impressora no Windows.

Eu criei esta ferramenta para agilizar meu trabalho no suporte, em vez de repetir os mesmos passos manuais a cada chamado de impressora travada. Ela foi desenvolvida com o auxílio de IA, e usei o projeto para praticar Python e entender como funcionam os serviços de impressão do Windows.

## O que ele faz
- Reúne em uma única janela as ações de manutenção mais usadas em erros de impressora
- Limpar a fila de impressão
- Reiniciar o serviço de spooler de impressão
- Remoção e instalação rápida de impressora

## Tecnologias
- Python 3
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) (interface gráfica)
- [pywin32](https://github.com/mhammond/pywin32) (integração com o Windows)
- [psutil](https://github.com/giampaolo/psutil) (informações de processos e serviços)

## Requisitos
- Windows
- Python 3.9 ou superior
- Permissão de administrador (necessária para mexer em serviços do Windows)

## Como rodar

1. Clone o repositório:
```bash
   git clone https://github.com/th4ylor/Printer-Support-Tools.git
   cd Printer-Support-Tools
```

2. (Opcional) Crie e ative um ambiente virtual:
```bash
   python -m venv venv
   venv\Scripts\activate
```

3. Instale as dependências:
```bash
   pip install -r requirements.txt
```

4. Execute o aplicativo (de preferência como administrador):
```bash
   python main.py
```

## Estrutura do projeto

```
Printer-Support-Tools/
├── main.py            # ponto de entrada do aplicativo
├── plataforma/        # código do app (interface e lógica)
├── requirements.txt   # dependências
└── LICENSE
```

## Aviso
Este é um projeto pessoal, criado para uso no meu dia a dia de trabalho. Use por sua conta e risco e teste primeiro em um computador que não seja crítico.

## Licença
Distribuído sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## Autor
Feito por [th4ylor](https://github.com/th4ylor).
