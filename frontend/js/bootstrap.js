/* Cognix · aviso visível caso a interface não consiga inicializar. */
(() => {
  let shown = false;
  function report(reason) {
    const root = document.getElementById('root');
    if (shown || !root || !root.querySelector('.loading')) return;
    shown = true;
    root.replaceChildren();
    const box = document.createElement('div');
    box.style.cssText = 'max-width:620px;margin:12vh auto;padding:32px;font:15px/1.6 Segoe UI,Arial,sans-serif;color:#20283d;background:#fff;border:1px solid #d9e0ea;border-radius:14px;box-shadow:0 10px 32px #15223f10';
    const title = document.createElement('h1');
    title.textContent = 'O Cognix não conseguiu iniciar';
    title.style.cssText = 'font-size:22px;margin:0 0 14px';
    const explain = document.createElement('p');
    explain.textContent = 'A página carregou, mas houve um erro na interface. Atualize com Ctrl+F5. Se continuar, copie o detalhe abaixo e informe ao suporte.';
    const detail = document.createElement('pre');
    detail.textContent = String(reason || 'Falha na inicialização.');
    detail.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6fa;padding:12px;border-radius:8px;font-size:12px';
    const retry = document.createElement('button');
    retry.textContent = 'Tentar novamente';
    retry.style.cssText='background:#394e96;color:#fff;border:0;border-radius:8px;padding:10px 16px;cursor:pointer';
    retry.addEventListener('click', () => location.reload());
    box.append(title, explain, detail, retry);
    root.append(box);
  }
  addEventListener('error', (ev) => {
    if (ev.target && ev.target !== window && ev.target.tagName === 'SCRIPT') {
      report('Não foi possível carregar o JavaScript da interface.');
    } else if (ev.error || ev.message) {
      report(ev.error?.message || ev.message);
    }
  }, true);
  addEventListener('unhandledrejection', ev => report(ev.reason?.message || 'Erro inesperado na inicialização.'));
  setTimeout(() => report('A tela não respondeu. Verifique o terminal do Cognix e atualize a página.'), 12000);
})();
