"use strict";
(() => {
  const el = id => document.getElementById(id);
  const labels = {not_configured:"Servico ativo; credencial Anycubic ainda nao configurada.",not_tested:"Credencial configurada; consulta ainda nao testada.",ok:"Consulta a conta concluida. Isso nao significa que todas as impressoras estejam online.",authentication_failed:"A Anycubic nao aceitou a sessao. Renove a credencial na hospedagem.",timeout:"Tempo de consulta esgotado. Dados anteriores nao sao leitura atual.",cloud_error:"Falha na consulta Anycubic. Pode haver incompatibilidade ou indisponibilidade; dados anteriores nao sao atuais."};
  let busy = false, timer;
  const line = (list, title, value) => {
    const dt = document.createElement("dt"), dd = document.createElement("dd");
    dt.textContent = title; dd.textContent = value === null || value === undefined || value === "" ? "Indisponivel nesta leitura" : String(value);
    list.append(dt, dd);
  };
  function render(data) {
    if (!data || !Array.isArray(data.printers) || !(data.state in labels)) throw Error("invalid_response");
    el("status").textContent = labels[data.state];
    el("updated").textContent = data.last_success ? "Ultima consulta bem-sucedida: " + new Date(data.last_success).toLocaleString("pt-BR") + (data.stale ? " — DADOS ANTERIORES" : " — horario da consulta, nao da telemetria da maquina") : "Nenhuma consulta concluida.";
    el("count").textContent = data.last_success ? data.printers.length + " impressora(s) retornada(s). Esperadas: 2." + (data.printers.length !== 2 ? " Confira a conta e o vinculo das maquinas." : "") : "";
    el("cards").replaceChildren();
    for (const p of data.printers) {
      const card = document.createElement("article"), heading = document.createElement("h2"), list = document.createElement("dl");
      card.className = "card"; heading.textContent = p.name;
      line(list,"Identificador da impressora",p.id);
      line(list,data.stale ? "Ultimo estado recebido (antigo)" : "Estado informado pela API",p.status);
      line(list,"Arquivo",p.filename); line(list,"Progresso (%)",p.progress_percent);
      line(list,"Tempo decorrido (min)",p.elapsed_minutes); line(list,"Tempo restante (min)",p.remaining_minutes);
      line(list,"Bico (graus C)",p.nozzle_celsius); line(list,"Mesa (graus C)",p.bed_celsius);
      card.append(heading,list); el("cards").append(card);
    }
  }
  async function load() {
    if (busy) return;
    busy = true; el("test").disabled = true;
    el("status").textContent = "Consultando; aguarde ate 40 segundos...";
    try {
      const response = await fetch("/api/printers", {cache:"no-store",credentials:"same-origin",signal:AbortSignal.timeout(40000)});
      if (response.status === 401) throw Error("login");
      if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) throw Error("backend");
      render(await response.json());
    } catch (error) {
      el("status").textContent = error.message === "login" ? "Autenticacao do painel necessaria. Reabra o endereco do servico." : "Nao foi possivel consultar o servico. No GitHub Pages o backend nao esta disponivel: abra o endereco HTTPS da hospedagem. Se ja estiver nele, verifique a disponibilidade.";
      el("cards").replaceChildren(); el("count").textContent = "";
      el("updated").textContent = "Sem leitura atual confirmada.";
      el("auto").checked = false; clearInterval(timer);
    } finally {busy = false; el("test").disabled = false;}
  }
  el("test").onclick = load;
  el("auto").onchange = () => { clearInterval(timer); if (el("auto").checked) { load(); timer = setInterval(() => {if (!document.hidden) load();},60000); } };
  function tab(factory) {
    el("factory").hidden = !factory; el("monitor").hidden = factory;
    el("tabFactory").setAttribute("aria-selected",String(factory)); el("tabMonitor").setAttribute("aria-selected",String(!factory));
    if(factory && !el("factoryFrame").getAttribute("src")) el("factoryFrame").src = "index.html";
  }
  el("tabFactory").onclick = () => tab(true); el("tabMonitor").onclick = () => tab(false);
})();
