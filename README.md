# Verificador NFC-e

Automação para monitoramento, cópia e organização de arquivos XML de NFC-e, com interface gráfica, histórico, validação e execução em segundo plano.

## Funcionalidades
- **Monitoramento automático** de uma pasta de origem para arquivos XML de NFC-e
- **Cópia inteligente** dos arquivos para estrutura organizada por ano, PDV e mês
- **Validação de integridade** dos arquivos XML antes da cópia
- **Proteção contra sobrescrita** - não sobrescreve arquivos já existentes
- **Registro detalhado** de todas as operações em log.txt (apenas alterações reais)
- **Histórico com filtros** por data e status na aba dedicada
- **Execução em segundo plano** via bandeja do sistema (systray)
- **Interface gráfica moderna** com PyQt5 e abas organizadas
- **Configuração persistente** em config.json
- **Cópia e validação em paralelo** para alto desempenho
- **Log auto-gerenciado** com limite de 1MB

## Comportamento do Sistema

### Inicialização
- Monitoramento inicia automaticamente ao abrir o executável
- Carrega configurações salvas (pastas, intervalo)
- Botão mostra "Parar Monitoramento" quando ativo

### Monitoramento Contínuo
- Verifica pasta de origem no intervalo configurado (padrão: 10 segundos)
- Para cada subpasta de mês (ex: "Mes 07"), procura arquivos XML
- Extrai PDV do nome do arquivo (posições 23-25)
- Cria estrutura: `NFCE/ANO/PDV-XX/MES XX`
- Copia arquivos (mantém originais na origem)

### Validações
- **XML Inválido:** Não copia, registra erro
- **Já existe:** Pula arquivo, não sobrescreve
- **Copiado:** Transferência bem-sucedida
- **Erro:** Falha na cópia, registra detalhes

### Interface
- **Aba "Monitoramento":** Status em tempo real
- **Aba "Histórico":** Filtros por data/status
- **Status geral:** "Verificados" quando sem atualizações
- **Controle manual:** Botão para pausar/retomar

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
3. (Opcional) Para compilar para .exe:
   ```bash
   pip install auto-py-to-exe
   ```

## Uso
1. Execute o script principal:
   ```bash
   python main.py
   ```
2. Configure pasta de origem, destino e intervalo pela interface
3. O monitoramento inicia automaticamente
4. Minimize para bandeja do sistema se necessário
5. Consulte histórico na aba "Histórico"

## Configuração
- Configurações salvas automaticamente em `config.json`
- Intervalo ajustável em tempo real
- Pastas de origem/destino configuráveis

## Arquivos Gerados
- `config.json`: Configurações do usuário
- `log.txt`: Histórico de operações (máx 1MB)

## Observações
- Valida XML antes de copiar
- Não sobrescreve arquivos existentes
- Log registra apenas operações com alteração
- Interface thread-safe para estabilidade
- Suporte a ícone customizado (icon.ico)

## Licença
Este projeto é livre para uso e modificação. 