# Monitoramento Anycubic no painel — primeira implementacao

## Estado real
Codigo inicial, NAO homologado com as duas Kobra X. Nenhum servico foi publicado por este commit. Nenhuma credencial real foi incluida. O index.html existente da fabrica nao e alterado.

A nova entrada e /fabrica/conexao.html: navegacao entre monitoramento e gestao existente (iframe de index.html na mesma origem). A entrada antiga continua funcionando como antes e nao recebe automaticamente um novo item de menu. A autenticacao protege apenas a instancia hospedada pelo backend, nao o GitHub Pages publico.

## O que esta implementado
- Servidor HTTP com autenticacao Basic em todas as rotas de dados e paginas; credencial do painel separada da Anycubic.
- ANYCUBIC_TOKEN lido somente do ambiente do servidor, nunca de localStorage, URL ou formulario do site.
- Consulta por check_api_tokens e list_my_printers da biblioteca comunitaria anycubic-cloud-api 0.4.37. Sem connect MQTT ou comandos de impressao.
- Consulta HTTP inicial de identificacao e current_status. Progresso, arquivo, temperaturas e tempos ficam explicitamente indisponiveis: ainda precisam de mapeamento e teste real. Nao confundir ultimo trabalho concluido com trabalho atual.
- Intervalo minimo de 60 segundos por processo, lock de consulta, timeout, ultima consulta bem-sucedida e sinalizacao de falha/dados anteriores.
- Esperadas duas impressoras, mas sem filtrar ou esconder outras retornadas pela conta. Vinculo por id, nao pelo nome.
- Sem dump de payload ou de excecoes da biblioteca nas respostas/logs. /healthz e publico e informa somente vida do processo, nao conexao com impressoras.
- GET /api/connection mostra o estado sem consultar a nuvem. GET /api/printers executa leitura respeitando o intervalo. Escritas HTTP sao rejeitadas.

## Hospedar pelo navegador, sem PowerShell
1. Confirme o commit desta implementacao na branch integracao-anycubic.
2. Em um provedor com Docker e HTTPS (por exemplo Render), conecte este repositorio e selecione explicitamente a branch integracao-anycubic. Se usar Blueprint, o arquivo render.yaml esta pronto; confirme a branch usada antes de criar o servico.
3. Escolha a modalidade e revise eventuais custos antes de confirmar a criacao na hospedagem. Nenhum plano pago e contratado por este codigo.
4. Nas variaveis SECRETAS da hospedagem configure PANEL_USER, PANEL_PASSWORD (senha exclusiva e aleatoria de pelo menos 16 caracteres) e ANYCUBIC_TOKEN (sessao autorizada do Slicer Next). Nao use a senha da Anycubic como senha do painel.
5. Nao cole o token em chat, commits, issues ou campos publicos. O metodo de obtencao do token precisa ser validado na instalacao do Slicer antes da ativacao. Nunca envie o arquivo de configuracao inteiro.
6. Publique usando o Dockerfile da raiz. Abra somente o endereco HTTPS fornecido, entre com as credenciais do PAINEL e use Testar conexao.
7. Use uma unica instancia e um unico processo inicialmente; o cache nao e compartilhado entre replicas.

O frontend nao configura segredos da hospedagem: isso e feito no painel do provedor, pelo navegador. Nenhum login automatico na Anycubic com senha foi implementado. Se a sessao expirar, substitua a variavel e reinicie. Remover ANYCUBIC_TOKEN e reiniciar desconecta o servico. Ao encerrar uso em computador compartilhado, feche todas as janelas: o navegador pode reter a autenticacao Basic. Use HTTPS obrigatoriamente; nao exponha a porta HTTP diretamente na internet.

## Dados da fabrica: cuidado com a origem
O sistema de gestao continua local, nao multiusuario. Abrir no novo dominio cria outro contexto de localStorage e NAO transfere os dados do GitHub Pages. Exporte o backup na versao antiga antes de qualquer mudanca. A versao atual nao tem restauracao/migracao pronta: nao comece lancamentos na copia do novo dominio antes de implementar e testar essa etapa. O monitoramento pode ser testado sem fazer lancamentos. Este commit nao apaga nem altera os dados antigos.

## Validacao antes de chamar de operacional
- [ ] Build Docker instala a dependencia fixada sem conflitos.
- [ ] Sem senha configurada o servidor bloqueia o acesso (503).
- [ ] Sem autenticacao nenhuma impressora ou pagina privada e retornada (401).
- [ ] Sem token: estado not_configured, sem dados inventados.
- [ ] Token autorizado: dois IDs diferentes, nomes e estados conferidos no Slicer.
- [ ] Uma maquina parada e outra imprimindo: comparar estados sem inferir online pelo sucesso da consulta.
- [ ] Credencial expirada/rede indisponivel: falha visivel, nunca estado antigo apresentado como atual.
- [ ] Repetir consulta antes de 60 segundos nao faz nova chamada cloud.
- [ ] Homologar telas em celular e Windows; iframe e autenticacao no navegador real.
- [ ] Validar progresso/arquivo/temperaturas/tempos em uma etapa posterior antes de preencher esses campos.

Testes unitarios: python -m unittest discover -s integracao -v. Esses testes nao substituem Docker, navegador, auditoria da dependencia nem acesso real a Anycubic. A biblioteca e comunitaria e pode mudar de comportamento. As credenciais de aplicacao internas da dependencia tambem merecem revisao antes de uso em producao; a exclusao de MQTT nao equivale a auditoria de seguranca completa.

Fonte do contrato inicial: https://pypi.org/project/anycubic-cloud-api/0.4.37/
