# Multicontas Anycubic — teste

Entrada: /fabrica/contas.html. O Blueprint inicia python integracao/multi_server.py; os arquivos antigos ficam preservados, mas conexao.html e /api/printers nao sao usados pelo novo servidor.

Implementa adicionar/validar sessao, renovar manualmente, consultar, filtrar e selecionar impressoras, remover credencial, exportar/restaurar backup cifrado. Ate 20 contas por painel administrativo compartilhado, sem isolamento multiusuario. Identificacao e estado apenas; progresso, arquivo, temperaturas e tempos continuam indisponiveis. Sem comandos de impressao/MQTT. Sem monitoramento garantido com navegador fechado.

Autorizacao inicial NAO automatizada: sessao deve ser fornecida pelo usuario. Leitura opcional de .conf ocorre apenas no navegador, por selecao explicita. Somente access_token JWT inequivoco e enviado apos consentimento; arquivo inteiro nao e enviado. Nao busca pastas, descriptografa config ou le memoria. Nao e OAuth oficial. Nao ha renovacao automatica persistente de tokens.

## Banco e hospedagem
A sincronizacao do Blueprint pode criar PostgreSQL FREE fabrica3d-contas-teste e reiniciar o servico. Banco gratuito expira em 30 dias, sem backup automatico; depois da expiracao fica inacessivel e e excluido apos a carencia de 14 dias sem upgrade. Nao ha upgrade pago automatico neste codigo. Web Free dorme e possui limites de uso/banda. Apenas teste, nao producao.

Fernet cifra tokens/metadados no banco. VAULT_KEY aleatoria fica separada no ambiente do Render. Preserve-a em gerenciador de senhas: perda/troca impede abrir contas e backups. generateValue preserva senhas existentes. Nenhuma credencial real no repositorio.

GET nunca retorna token. POST exige Basic, JSON, cabecalho X-Panel-Action e Origin identica; HTTPS obrigatorio. Sem logs de payload cloud. Basic pode permanecer na memoria do navegador: feche as janelas em computadores compartilhados. Excluir conta aqui nao revoga a sessao Anycubic. Token pode ter permissoes maiores que o programa expoe. Dependencia comunitaria sem auditoria integral.

Backup cifrado exige mesma VAULT_KEY; restauracao valida tudo antes de upsert transacional, substitui IDs coincidentes e preserva outros. Estados sao refeitos apos reinicio; data de consulta nao e de telemetria; falhas e dados antigos sao sinalizados. Intervalo minimo de 60 segundos por conta/processo, uma consulta por vez. Mesma sessao cadastrada duas vezes pode duplicar maquinas.

Validacao local: sete testes com cloud simulada e SQLite substituindo SQL; sintaxe Python/JavaScript. NAO homologados: Docker, PostgreSQL real, navegador e leitura real das Kobra X. Testar persistencia apos restart, backup/restore, falhas, renovacao, selecao, remocao e estados contra Slicer antes de uso operacional. Pedidos/estoque continuam no localStorage, sem migracao.

Fontes: https://render.com/docs/free e https://render.com/docs/blueprint-spec
