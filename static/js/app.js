/*
 * Comportamento no navegador (Alpine.js). Substitui os componentes "use client"
 * do projeto em React: wizard de nova ocorrência, filtros do portal, sino de
 * notificações, modais de confirmação etc. Os dados vêm do servidor (Django).
 */

// ---------------------------------------------------------------- utilidades

function csrfToken() {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

async function postForm(url, dados) {
  const fd = dados instanceof FormData ? dados : new FormData();
  if (!(dados instanceof FormData)) {
    for (const [k, v] of Object.entries(dados || {})) {
      (Array.isArray(v) ? v : [v]).forEach((x) => fd.append(k, x));
    }
  }
  const r = await fetch(url, {
    method: "POST",
    body: fd,
    headers: { "X-CSRFToken": csrfToken(), Accept: "application/json" },
    credentials: "same-origin",
  });
  return r.ok ? r.json() : null;
}

function lerStorage(chave) {
  try {
    return localStorage.getItem(chave);
  } catch {
    return null;
  }
}

function gravarStorage(chave, valor) {
  try {
    if (valor === null) localStorage.removeItem(chave);
    else localStorage.setItem(chave, valor);
  } catch {
    /* localStorage indisponível */
  }
}

// Ícones Lucide: troca <i data-lucide> por SVG, inclusive em conteúdo que o
// Alpine cria depois (x-if / x-for).
function desenharIcones() {
  if (window.lucide) window.lucide.createIcons();
}
let iconesAgendados = false;
new MutationObserver(() => {
  if (iconesAgendados) return;
  iconesAgendados = true;
  requestAnimationFrame(() => {
    iconesAgendados = false;
    desenharIcones();
  });
}).observe(document.documentElement, { childList: true, subtree: true });
document.addEventListener("DOMContentLoaded", desenharIcones);

// ---------------------------------------------------------------- anexos
// Fotos de celular têm vários MB, e a Vercel limita o corpo da requisição a
// 4,5 MB (spec 015). Ao escolher arquivos num <input data-comprimir>, as fotos
// são reduzidas aqui mesmo (port do imagem.ts do projeto original). No envio,
// formulários com data-anexos-limite conferem a soma antes de mandar.

const FOTO_MAX_LADO = 1600;
const FOTO_QUALIDADE = 0.8;
const FOTO_SEM_COMPRIMIR_ATE = 1_500_000; // bytes

/** Reduz uma foto (JPEG). Não-imagem, GIF, foto pequena ou qualquer falha: devolve o original. */
async function comprimirImagem(arquivo) {
  if (!arquivo.type.startsWith("image/") || arquivo.type === "image/gif") return arquivo;
  try {
    const bitmap = await createImageBitmap(arquivo);
    const escala = Math.min(1, FOTO_MAX_LADO / Math.max(bitmap.width, bitmap.height));
    if (escala >= 1 && arquivo.size < FOTO_SEM_COMPRIMIR_ATE) {
      bitmap.close?.();
      return arquivo;
    }
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * escala);
    canvas.height = Math.round(bitmap.height * escala);
    canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close?.();
    const blob = await new Promise((ok) => canvas.toBlob(ok, "image/jpeg", FOTO_QUALIDADE));
    if (!blob || blob.size >= arquivo.size) return arquivo;
    const nome = arquivo.name.replace(/\.[^.]+$/, "") + ".jpg";
    return new File([blob], nome, { type: "image/jpeg", lastModified: Date.now() });
  } catch {
    return arquivo;
  }
}

function mostrarErroUpload(form, mensagem) {
  const el = form.querySelector("[data-erro-upload]");
  if (!el) {
    if (mensagem) window.alert(mensagem);
    return;
  }
  el.textContent = mensagem || "";
  el.hidden = !mensagem;
}

function formatarMb(bytes) {
  return (bytes / (1024 * 1024)).toFixed(1).replace(".", ",");
}

document.addEventListener("change", async (e) => {
  const input = e.target;
  if (!(input instanceof HTMLInputElement) || input.type !== "file" || !input.hasAttribute("data-comprimir")) return;
  const arquivos = Array.from(input.files || []);
  if (!arquivos.some((f) => f.type.startsWith("image/"))) return;
  const form = input.form;
  if (form) {
    form.dataset.comprimindo = "1";
    mostrarErroUpload(form, null);
  }
  try {
    const prontos = await Promise.all(arquivos.map(comprimirImagem));
    const dt = new DataTransfer();
    prontos.forEach((f) => dt.items.add(f));
    input.files = dt.files;
  } finally {
    if (form) delete form.dataset.comprimindo;
  }
});

// Fase de bolha: roda depois das validações do Alpine (@submit) e só age se
// o envio ainda for seguir.
document.addEventListener("submit", (e) => {
  const form = e.target;
  if (!(form instanceof HTMLFormElement) || !form.dataset.anexosLimite || e.defaultPrevented) return;
  const cancelar = (mensagem) => {
    e.preventDefault();
    mostrarErroUpload(form, mensagem);
    form.dispatchEvent(new CustomEvent("envio-cancelado"));
  };
  if (form.dataset.comprimindo) {
    cancelar("Aguarde: as fotos ainda estão sendo preparadas.");
    return;
  }
  const limite = Number(form.dataset.anexosLimite);
  let total = 0;
  for (const campo of form.elements) {
    if (campo.type === "file") for (const f of campo.files || []) total += f.size;
  }
  if (limite && total > limite) {
    cancelar(`Os anexos somam ${formatarMb(total)} MB; o limite por envio é ${formatarMb(limite)} MB. Envie em mais de uma mensagem.`);
    return;
  }
  mostrarErroUpload(form, null);
});

// ---------------------------------------------------------------- componentes

document.addEventListener("alpine:init", () => {
  /** Alternar tema claro/escuro (salvo no navegador). */
  Alpine.data("tema", () => ({
    escuro: document.documentElement.classList.contains("dark"),
    alternar() {
      this.escuro = !this.escuro;
      document.documentElement.classList.toggle("dark", this.escuro);
      gravarStorage("theme", this.escuro ? "dark" : "light");
    },
  }));

  /** Mostrar/ocultar senha. */
  Alpine.data("campoSenha", () => ({ ver: false }));

  /** Bloco que abre/fecha (ex.: "Nova empresa"). */
  Alpine.data("abrivel", (inicial = false) => ({ aberto: inicial }));

  /**
   * Formulário com confirmação em modal. Use em <form x-data="confirmar"
   * @submit="interceptar">; o modal chama confirmar().
   */
  Alpine.data("confirmar", () => ({
    aberto: false,
    ok: false,
    enviando: false,
    init() {
      // Guardado aqui porque o modal é teleportado para o <body>.
      this.form = this.$el;
    },
    interceptar(e) {
      if (!this.ok) {
        e.preventDefault();
        this.aberto = true;
        return;
      }
      this.enviando = true;
    },
    confirmar() {
      this.ok = true;
      this.form.requestSubmit();
    },
  }));

  /** Botão de envio que mostra "Aguarde…" (evita duplo clique). */
  Alpine.data("enviando", () => ({ enviando: false }));

  /** Sino de notificações do cabeçalho (busca a cada 30s). */
  Alpine.data("sino", (naoLidas) => ({
    aberto: false,
    itens: [],
    naoLidas,
    carregado: false,
    init() {
      setInterval(() => {
        if (document.visibilityState === "visible") this.atualizar();
      }, 30000);
      const aoVoltar = () => {
        if (document.visibilityState === "visible") this.atualizar();
      };
      document.addEventListener("visibilitychange", aoVoltar);
      window.addEventListener("focus", aoVoltar);
    },
    async atualizar() {
      try {
        const r = await fetch("/notificacoes/recentes", {
          headers: { Accept: "application/json" },
          credentials: "same-origin",
        });
        if (!r.ok) return null;
        const d = await r.json();
        this.itens = d.itens;
        this.naoLidas = d.naoLidas;
        this.carregado = true;
        return d.itens;
      } catch {
        return null;
      }
    },
    async alternar() {
      this.aberto = !this.aberto;
      if (!this.aberto) return;
      // Marca como lidas só as que aparecem na lista — nunca uma não vista.
      const lista = await this.atualizar();
      const ids = (lista || []).filter((n) => !n.lida).map((n) => n.id);
      if (ids.length === 0) return;
      postForm("/notificacoes/marcar-lidas", { ids });
      this.naoLidas = Math.max(0, this.naoLidas - ids.length);
    },
  }));

  /** Lista de ocorrências do portal: filtros no navegador. */
  Alpine.data("portalLista", (meta, filtroInicial, rotulosTipo) => ({
    meta,
    rotulosTipo,
    status: filtroInicial === "aprovar" ? "resolvida" : "todas",
    escopo: filtroInicial === "aprovar" ? "minhas" : "empresa",
    q: "",
    cat: "",
    de: "",
    ate: "",
    filtrosAbertos: false,
    get base() {
      const termo = this.q.trim().toLowerCase();
      return this.meta.filter(
        (o) =>
          (this.escopo === "empresa" || o.minha) &&
          (!termo || o.texto.includes(termo)) &&
          (!this.cat || o.tipo === this.cat) &&
          (!this.de || o.dia >= this.de) &&
          (!this.ate || o.dia <= this.ate),
      );
    },
    get exibidas() {
      return new Set(
        this.base.filter((o) => this.status === "todas" || o.status === this.status).map((o) => o.id),
      );
    },
    contagem(s) {
      return s === "todas" ? this.base.length : this.base.filter((o) => o.status === s).length;
    },
    get nAvancados() {
      return [this.cat, this.de, this.ate].filter(Boolean).length;
    },
    get temFiltro() {
      return this.q !== "" || this.nAvancados > 0 || this.status !== "todas";
    },
    diaBonito(d) {
      return d.split("-").reverse().join("/");
    },
    verPendentes() {
      this.status = "resolvida";
      this.escopo = "minhas";
    },
    limpar() {
      this.status = "todas";
      this.q = "";
      this.cat = "";
      this.de = "";
      this.ate = "";
    },
  }));

  /** Painel de avisos do portal: alertas primeiro, info pode ser dispensado. */
  Alpine.data("avisosPainel", (avisos) => ({
    avisos, // [{id, tipo}] já ordenados (alertas primeiro)
    dispensados: new Set((lerStorage("avisos-dispensados") || "").split(",").filter(Boolean)),
    todos: false,
    get visiveis() {
      return this.avisos.filter((a) => a.tipo === "alerta" || !this.dispensados.has(a.id)).map((a) => a.id);
    },
    get escondidos() {
      return this.avisos.length - this.visiveis.length;
    },
    get alertas() {
      return this.avisos.filter((a) => a.tipo === "alerta").length;
    },
    mostrar(id) {
      const v = this.todos ? this.visiveis : this.visiveis.slice(0, 3);
      return v.includes(id);
    },
    dispensar(id) {
      this.dispensados = new Set([...this.dispensados, id]);
      gravarStorage("avisos-dispensados", [...this.dispensados].join(","));
    },
    restaurar() {
      this.dispensados = new Set();
      gravarStorage("avisos-dispensados", null);
    },
  }));

  /** Formulário de mensagem (nota interna x resposta ao cliente). */
  Alpine.data("mensagemForm", (opts) => ({
    interna: opts.interna,
    permiteNotaInterna: opts.permiteNotaInterna,
    avisaBump: opts.avisaBump,
    arquivos: [],
    modalBump: false,
    confirmado: false,
    enviando: false,
    init() {
      this.form = this.$el;
    },
    escolher(e) {
      this.arquivos = Array.from(e.target.files || []).map((f) => f.name);
    },
    limparArquivos() {
      this.$refs.arquivos.value = "";
      this.arquivos = [];
    },
    onSubmit(e) {
      // Nota interna não movimenta o status → não precisa confirmar.
      if (this.avisaBump && !this.interna && !this.confirmado) {
        e.preventDefault();
        this.modalBump = true;
        return;
      }
      this.enviando = true;
    },
    confirmarEnvio() {
      this.confirmado = true;
      this.modalBump = false;
      this.form.requestSubmit();
    },
  }));

  /** Controles do operador: status/prioridade/responsável. */
  Alpine.data("controles", (opts) => ({
    statusSel: opts.status,
    statusAtual: opts.status,
    atribuidoSel: opts.atribuido,
    temTratativa: opts.temTratativa,
    modal: false,
    confirmado: false,
    init() {
      this.form = this.$el;
    },
    get faltaResponsavel() {
      return this.atribuidoSel === "";
    },
    get bloqueado() {
      return this.statusSel !== this.statusAtual && (this.faltaResponsavel || !this.temTratativa);
    },
    get faltando() {
      return [
        this.faltaResponsavel && "defina um responsável",
        !this.temTratativa && "registre pelo menos uma mensagem para o cliente",
      ]
        .filter(Boolean)
        .join(" e ");
    },
    onSubmit(e) {
      // Confirma ao mudar PARA "resolvida" (vai para aprovação do cliente).
      if (this.statusSel === "resolvida" && this.statusAtual !== "resolvida" && !this.confirmado) {
        e.preventDefault();
        this.modal = true;
      }
    },
    confirmar() {
      this.confirmado = true;
      this.modal = false;
      this.form.requestSubmit();
    },
  }));

  /** Lixeira: seleção para exclusão definitiva. */
  Alpine.data("lixeira", (ids) => ({
    ids,
    sel: [],
    get todos() {
      return this.ids.length > 0 && this.sel.length === this.ids.length;
    },
    alternarTodos() {
      this.sel = this.todos ? [] : [...this.ids];
    },
  }));

  /** Reenviar convite (inline na tabela de usuários). */
  Alpine.data("reenviar", (url) => ({
    pendente: false,
    mensagem: null,
    erro: null,
    async enviar() {
      this.erro = null;
      this.pendente = true;
      const r = await postForm(url, {});
      this.pendente = false;
      if (!r) this.erro = "Não foi possível reenviar.";
      else if (r.error) this.erro = r.error;
      else this.mensagem = r.mensagem || "Convite reenviado.";
    },
  }));

  /** Novo aviso com prévia ao vivo. */
  Alpine.data("avisoForm", (v) => ({
    aberto: v.aberto,
    titulo: v.titulo || "",
    mensagem: v.mensagem || "",
    tipo: v.tipo || "info",
    validade: v.validade || "",
    get validadeBonita() {
      return this.validade ? this.validade.split("-").reverse().join("/") : "";
    },
  }));

  /** Principais motivos: alterna entre contar ocorrências ou itens. */
  Alpine.data("motivos", () => ({ modo: "ocorrencias" }));

  /** Definir senha: confere se as duas senhas batem. */
  Alpine.data("definirSenha", () => ({
    senha: "",
    confirma: "",
    get conferem() {
      return this.confirma.length > 0 && this.senha === this.confirma;
    },
    get naoConferem() {
      return this.confirma.length > 0 && this.senha !== this.confirma;
    },
  }));

  /** Wizard de nova ocorrência (2 passos, rascunho no navegador). */
  Alpine.data("novaOcorrencia", (config, inicial) => ({
    config,
    passo: inicial ? 2 : 1,
    tipo: inicial?.tipo || "",
    refTipo: inicial?.refTipo || "",
    referencia: inicial?.referencia || "",
    itens: inicial?.itens || [],
    descricaoGeral: inicial?.descricao || "",

    // Rascunho / edição do produto.
    catProduto: "avaria",
    sinalVolume: "",
    codigo: "",
    descricao: "",
    quantidade: "",
    editandoIndex: null,
    produtoErro: null,

    anexosFotos: 0,
    anexoErro: null,
    descricaoErro: null,
    importMsg: null,
    importando: false,
    duplicata: null,
    rascunho: null,
    enviando: false,

    DRAFT_KEY: "nova-ocorrencia-rascunho",

    init() {
      // Oferece retomar um rascunho salvo (não aplica sozinho).
      if (!inicial) {
        try {
          const d = JSON.parse(lerStorage(this.DRAFT_KEY) || "null");
          if (d && (d.tipo || d.referencia || (d.itens?.length ?? 0) > 0 || d.descricao)) this.rascunho = d;
        } catch {
          /* rascunho inválido */
        }
      }
      for (const campo of ["tipo", "refTipo", "referencia", "descricaoGeral", "itens"]) {
        this.$watch(campo, () => this.salvarRascunho());
      }
    },

    // ----- derivados -----
    get exigeReferencia() {
      return this.tipo !== "" && this.config.comReferencia.includes(this.tipo);
    },
    get categoriaComProduto() {
      return this.tipo !== "" && this.config.comProdutos.includes(this.tipo);
    },
    get referenciaOk() {
      return this.refTipo !== "" && this.referencia.trim() !== "";
    },
    get podeLancarProdutos() {
      return this.categoriaComProduto && this.referenciaOk;
    },
    get podeAvancar() {
      return this.tipo !== "" && (!this.exigeReferencia || this.referenciaOk);
    },
    get mostrarExtrato() {
      return this.passo === 2 && this.categoriaComProduto;
    },
    get precisaFoto() {
      return this.itens.some((it) => this.config.exigemFoto.includes(it.categoria));
    },
    get dispensaDadosProduto() {
      return this.config.dispensamDados.includes(this.catProduto);
    },
    get pedeSinalVolume() {
      return this.config.comSinalVolume.includes(this.catProduto);
    },
    get itensJson() {
      return JSON.stringify(this.podeLancarProdutos ? this.itens : []);
    },
    /** Sinal do item (mesma regra de labels.sinal_item): na troca de volume, vem do falta/sobra. */
    sinal(it) {
      const base = this.config.comSinalVolume.includes(it.categoria) ? it.sinal_volume : it.categoria;
      return base === "falta" ? "neg" : base === "sobra" ? "pos" : "neutro";
    },
    rotuloItem(it) {
      const rotulo = this.config.categoriaLabel[it.categoria];
      return it.sinal_volume ? `${rotulo} (${it.sinal_volume})` : rotulo;
    },

    // ----- rascunho -----
    salvarRascunho() {
      const vazio = !this.tipo && !this.referencia && this.itens.length === 0 && !this.descricaoGeral;
      gravarStorage(
        this.DRAFT_KEY,
        vazio
          ? null
          : JSON.stringify({
              tipo: this.tipo,
              refTipo: this.refTipo,
              referencia: this.referencia,
              descricao: this.descricaoGeral,
              itens: this.itens,
            }),
      );
    },
    aplicarRascunho() {
      const r = this.rascunho;
      if (!r) return;
      this.tipo = r.tipo || "";
      this.refTipo = r.refTipo || "";
      this.referencia = r.referencia || "";
      this.descricaoGeral = r.descricao || "";
      this.itens = r.itens || [];
      this.rascunho = null;
    },
    descartarRascunho() {
      gravarStorage(this.DRAFT_KEY, null);
      this.rascunho = null;
    },

    // ----- passo 1 -----
    trocarCategoria(novo) {
      this.tipo = novo;
      this.duplicata = null;
      if (!this.config.comProdutos.includes(novo)) {
        this.itens = [];
        this.limparProduto();
      }
    },
    escolherRefTipo(rt) {
      // Clicar na opção já selecionada desmarca.
      if (this.refTipo === rt) {
        this.refTipo = "";
        this.referencia = "";
      } else {
        this.refTipo = rt;
      }
    },
    async continuar() {
      if (!this.podeAvancar) return;
      this.passo = 2;
      if (this.referencia.trim()) {
        try {
          const r = await fetch(`/portal/nova/duplicata?referencia=${encodeURIComponent(this.referencia)}`, {
            headers: { Accept: "application/json" },
            credentials: "same-origin",
          });
          this.duplicata = r.ok ? (await r.json()).duplicata : null;
        } catch {
          this.duplicata = null;
        }
      }
    },

    // ----- produtos -----
    limparProduto() {
      this.catProduto = "avaria";
      this.sinalVolume = "";
      this.codigo = "";
      this.descricao = "";
      this.quantidade = "";
      this.editandoIndex = null;
      this.produtoErro = null;
    },
    salvarProduto() {
      const dispensa = this.dispensaDadosProduto;
      const digitada = parseInt(this.quantidade, 10);
      // Troca de volume: sem quantidade informada, assume 1 volume.
      const qtd = dispensa && !Number.isFinite(digitada) ? 1 : digitada;
      if (!dispensa) {
        if (!this.codigo.trim() || !this.descricao.trim() || !Number.isFinite(qtd) || qtd <= 0) {
          this.produtoErro = "Preencha código, descrição e uma quantidade maior que zero.";
          return;
        }
      } else if (!Number.isFinite(qtd) || qtd <= 0) {
        this.produtoErro = "Informe uma quantidade maior que zero.";
        return;
      }
      if (this.pedeSinalVolume && !this.sinalVolume) {
        this.produtoErro = "Informe se o volume está faltando ou sobrando.";
        return;
      }
      const novo = {
        categoria: this.catProduto,
        codigo: this.codigo.trim(),
        descricao: this.descricao.trim() || this.config.categoriaLabel.troca_volume,
        quantidade: qtd,
        sinal_volume: this.pedeSinalVolume ? this.sinalVolume : null,
      };
      if (this.editandoIndex !== null) {
        const copia = [...this.itens];
        copia[this.editandoIndex] = novo;
        this.itens = copia;
      } else {
        this.itens = [...this.itens, novo];
      }
      this.limparProduto();
    },
    editarProduto(i) {
      const it = this.itens[i];
      this.catProduto = it.categoria;
      this.sinalVolume = it.sinal_volume || "";
      this.codigo = it.codigo;
      this.descricao = it.descricao;
      this.quantidade = String(it.quantidade);
      this.editandoIndex = i;
      this.produtoErro = null;
    },
    removerProduto(i) {
      this.itens = this.itens.filter((_, idx) => idx !== i);
      if (this.editandoIndex === i) this.limparProduto();
    },
    async importarPlanilha(e) {
      const f = e.target.files?.[0];
      if (!f) return;
      this.importando = true;
      this.importMsg = null;
      const fd = new FormData();
      fd.append("file", f);
      const res = await postForm("/portal/nova/importar", fd);
      this.importando = false;
      e.target.value = "";
      if (!res) {
        this.importMsg = "Não foi possível ler o arquivo.";
        return;
      }
      if (res.erro) {
        this.importMsg = res.erro;
        return;
      }
      this.itens = [...this.itens, ...res.itens];
      this.importMsg =
        `${res.total} produto(s) importado(s)` + (res.ignoradas > 0 ? ` · ${res.ignoradas} linha(s) ignorada(s)` : "");
    },
    baixarModelo() {
      const csv =
        "codigo;nome;categoria;quantidade;sinal\n" +
        "001;Camisa azul;Avaria;1;\n" +
        "002;Camisa preta;Falta;10;\n" +
        "003;Caneca;Sobra;5;\n" +
        ";Volume 2 de 3;Troca de volume;1;Falta\n";
      const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8;" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = "modelo-produtos.csv";
      a.click();
      URL.revokeObjectURL(url);
    },

    // ----- anexos e envio -----
    contarFotos(e) {
      this.anexosFotos = Array.from(e.target.files || []).filter((f) => f.type.startsWith("image/")).length;
      if (this.anexosFotos > 0) this.anexoErro = null;
    },
    onEnviar(e) {
      if (!this.categoriaComProduto && this.descricaoGeral.trim().length < 10) {
        e.preventDefault();
        this.descricaoErro = "Descreva a ocorrência com pelo menos 10 caracteres.";
        return;
      }
      this.descricaoErro = null;
      if (this.precisaFoto && this.anexosFotos === 0) {
        e.preventDefault();
        this.anexoErro = "Anexe pelo menos uma foto mostrando a avaria/produto vencido/volume trocado.";
        return;
      }
      this.anexoErro = null;
      gravarStorage(this.DRAFT_KEY, null);
      this.enviando = true;
    },
  }));
});
