## Verificador NFC-e

Automação para monitoramento, cópia e organização de arquivos XML de NFC-e, com interface gráfica, histórico filtrável, validação e execução em segundo plano (bandeja do sistema).

## Funcionalidades
- **Monitoramento automático** da pasta de origem para arquivos XML de NFC-e
- **Cópia inteligente** para estrutura organizada por ano, PDV e mês: `NFCE/ANO/PDV-XXX/MES XX`
- **Validação de integridade** dos arquivos XML antes da cópia
- **Proteção contra sobrescrita**: não sobrescreve arquivos já existentes
- **Registro detalhado** de todas as operações em `log.txt` (todos os status)
- **Histórico com filtros** por data e status, com botão de limpar filtros
- **Execução em segundo plano** via bandeja do sistema (systray)
- **Interface gráfica** com PyQt5 em abas
- **Configuração persistente** em `config.json`
- **Gerenciamento automático do log** com limite de 1MB

## Comportamento do Sistema

### Inicialização e Bandeja
- O monitoramento inicia automaticamente ao executar o app (se as pastas estiverem configuradas)
- O aplicativo inicia **minimizado na bandeja** quando está tudo configurado e funcionando
- A janela só é exibida automaticamente em situações de atenção: sem configuração, monitoramento parado ou erros
- Ao clicar no ícone da bandeja para abrir, a janela permanece aberta (não é minimizada automaticamente)

### Extração de PDV a partir do nome do arquivo
- Arquivos padrão NFC-e: usa posições 23–25 para o PDV (0-indexed 22–24)
  - Ex.: `35250802775652000123650310000000901564004651-NFCe.xml` → `PDV-031`
- Arquivos de inutilização (InutNFCe): usa posições 21–23 para o PDV (0-indexed 20–22)
  - Ex.: `35252434286900018265031000001542000001542-InutNFCe.xml` → `PDV-031`
- Ambos os tipos são organizados na mesma pasta `PDV-XXX`

### Monitoramento Contínuo
- Verifica a pasta de origem no intervalo configurado (padrão: 10 segundos)
- Para cada subpasta de mês (ex.: `Mes 07`), procura arquivos `.xml`
- Cria estrutura de destino: `NFCE/ANO/PDV-XXX/MES XX`
- Copia os arquivos mantendo os originais

### Validações e Status
- **XML Inválido**: não copia, registra no log
- **Já existe**: pula o arquivo, não sobrescreve, registra no log (se habilitado pelo fluxo atual)
- **Copiado**: transferência bem-sucedida
- **Erro**: registra falhas na cópia/validação

### Histórico
- Aba dedicada com filtros de Data e Status
- Quando o Status é **Todos**, a **data é ignorada** (lista todas as datas)
- Status disponíveis: `Todos`, `Copiado`, `Já existe`, `Erro`, `XML Inválido`
- Botão **Limpar Filtros** para resetar rapidamente (Data = hoje, Status = Todos)
- Exibe "Nenhum resultado" quando não houver linhas para os filtros aplicados

## Atualizações
- Verificação de versão mais recente no GitHub Releases
- Atualização assistida diretamente pelo aplicativo
- Versão atual: `1.0.3`

## Requisitos
- Python 3.7+
- PyQt5
- requests

## Instalação (desenvolvimento)
1. Clone este repositório:
   ```bash
   git clone <url-do-repositorio>
   ```
2. Instale as dependências:
   ```bash
   pip install pyqt5 requests
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
2. Configure pasta de origem, destino e intervalo pela interface (se não configurado, a janela será exibida)
3. O monitoramento inicia automaticamente; quando tudo estiver ok, o app permanece na bandeja
4. Clique no ícone da bandeja para abrir a janela quando desejar
5. Consulte o histórico na aba "Histórico"

## Configuração
- Configurações salvas automaticamente em `config.json`
- Chaves usadas: `origem`, `destino`, `intervalo`
- Intervalo ajustável em tempo real

## Arquivos Gerados
- `config.json`: configurações do usuário
- `log.txt`: histórico de operações (máx. 1MB)

## Observações
- Valida XML antes de copiar
- Não sobrescreve arquivos existentes
- Log registra todos os status relevantes
- Suporte a ícone customizado (`icon.ico`)

## Licença
Este projeto é livre para uso e modificação.
