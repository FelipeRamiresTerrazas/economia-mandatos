// Hover dos gráficos: linha vertical e caixa com os valores do ponto mais próximo de cada série.
document.querySelectorAll(".grafico").forEach(function (g) {
  var svg = g.querySelector("svg");
  var alvo = g.querySelector(".alvo");
  var cruz = g.querySelector(".cruz");
  var tip = g.querySelector(".tooltip");
  var dados = JSON.parse(g.querySelector(".dados").textContent);
  var W = svg.viewBox.baseVal.width;

  function maisProximo(pts, x) {
    var melhor = null, dist = Infinity;
    for (var i = 0; i < pts.length; i++) {
      var d = Math.abs(pts[i][0] - x);
      if (d < dist) { dist = d; melhor = pts[i]; }
    }
    return { p: melhor, d: dist };
  }

  function mover(ev) {
    var r = svg.getBoundingClientRect();
    var escala = r.width / W;
    var x = (ev.clientX - r.left) / escala;
    var ref = null, linhas = [];
    dados.series.forEach(function (s) {
      var m = maisProximo(s.p, x);
      if (!m.p) return;
      if (!ref || m.d < ref.d) ref = m;
    });
    if (!ref) return;
    var rotulo = ref.p[2];
    dados.series.forEach(function (s) {
      var hit = s.p.filter(function (p) { return p[2] === rotulo; })[0];
      if (hit) linhas.push('<div><i class="chip s' + s.slot + '"></i>' + s.nome + '<span class="tv">' + hit[3] + "</span></div>");
    });
    cruz.setAttribute("x1", ref.p[0]);
    cruz.setAttribute("x2", ref.p[0]);
    cruz.setAttribute("visibility", "visible");
    tip.innerHTML = "<b>" + rotulo + " · " + dados.unidade + "</b>" + linhas.join("");
    tip.hidden = false;
    var px = ref.p[0] * escala, py = ref.p[1] * escala;
    var esquerda = px + 12;
    if (esquerda + tip.offsetWidth > r.width) esquerda = px - tip.offsetWidth - 12;
    tip.style.left = Math.max(0, esquerda) + "px";
    tip.style.top = Math.max(0, py - tip.offsetHeight / 2) + "px";
  }

  function sair() { cruz.setAttribute("visibility", "hidden"); tip.hidden = true; }
  alvo.addEventListener("mousemove", mover);
  alvo.addEventListener("mouseleave", sair);
  alvo.addEventListener("touchstart", function (e) { mover(e.touches[0]); }, { passive: true });
});
