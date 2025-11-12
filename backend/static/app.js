function showToast(msg){
  const wrap = document.getElementById('toasts'); if(!wrap) return;
  const el = document.createElement('div'); el.className='toast'; el.textContent=msg; wrap.appendChild(el);
  setTimeout(()=>{ el.style.opacity='0'; el.style.transform='translateY(8px)' }, 1700);
  setTimeout(()=>{ el.remove() }, 2100);
}
(function themeToggle(){
  const btn = document.getElementById('theme-toggle');
  const root = document.documentElement;
  function apply(mode){ root.setAttribute('data-theme', mode); localStorage.setItem('theme', mode); }
  apply(localStorage.getItem('theme') || 'dark');
  if (btn){ btn.addEventListener('click', ()=>{ apply((root.getAttribute('data-theme') || 'dark') === 'dark' ? 'light' : 'dark'); }); }
})();
