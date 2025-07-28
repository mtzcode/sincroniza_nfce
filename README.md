# Verificador NFC-e

Automação para monitoramento, cópia e organização de arquivos XML de NFC-e, com interface gráfica, histórico, validação e execução em segundo plano.

## Funcionalidades
- Monitoramento automático de uma pasta de origem para arquivos XML de NFC-e
- Cópia dos arquivos para uma estrutura organizada por ano, PDV e mês
- Validação de integridade dos arquivos XML antes da cópia
- Não sobrescreve arquivos já existentes no destino
- Registro de todas as operações em log.txt
- Aba de histórico com filtro por data e status
- Execução em segundo plano (bandeja do sistema)
- Interface gráfica moderna com PyQt5
- Configuração persistente em config.json
- Cópia e validação em paralelo para alto desempenho

## Requisitos
- Python 3.7+
- PyQt5

## Instalação
1. Clone este repositório:
   ```bash
   git clone <url-do-repositorio>
   ```
2. Instale as dependências:
   ```bash
   pip install pyqt5
   ```
3. (Opcional) Para compilar para .exe, use [auto-py-to-exe](https://github.com/brentvollebregt/auto-py-to-exe):
   ```bash
   pip install auto-py-to-exe
   ```

## Uso
1. Execute o script principal:
   ```bash
   python main.py
   ```
2. Configure a pasta de origem, destino e intervalo desejado pela interface.
3. O monitoramento inicia automaticamente. O programa pode ser minimizado para a bandeja do sistema.
4. Consulte o histórico de operações na aba "Histórico".

## Configuração
As configurações são salvas automaticamente no arquivo `config.json`.

## Log
Todas as operações são registradas em `log.txt` para auditoria e suporte.

## Observações
- O programa valida se o XML é bem formado antes de copiar.
- Arquivos já existentes não são sobrescritos.
- O histórico pode ser filtrado por data e status.
- Para personalizar o ícone da bandeja, coloque um arquivo `icon.ico` na pasta do executável.

## Licença
Este projeto é livre para uso e modificação. 