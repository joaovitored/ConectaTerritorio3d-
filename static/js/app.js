(() => {
  const app = document.getElementById('app');
  const toastEl = document.getElementById('toast');
  const state = {
    view: 'login',
    user: null,
    projects: [
      { name: 'Zoneamento urbano', place: 'Recife · PE', updated: 'Atualizado hoje', type: 'MAP', status: 'Em andamento' },
      { name: 'Bacia hidrográfica', place: 'São Francisco · PE', updated: 'Editado ontem', type: 'H₂O', status: 'Concluído' },
      { name: 'Uso e cobertura do solo', place: 'Jaboatão · PE', updated: 'Editado há 3 dias', type: 'GIS', status: 'Em andamento' },
      { name: 'Limites municipais', place: 'Região Metropolitana · PE', updated: 'Editado há 1 semana', type: 'MAP', status: 'Concluído' }
    ],
    layers: [
      { name: 'Elevação', desc: 'Relevo e altitude', color: '#279a7b', on: true },
      { name: 'Hidrografia', desc: 'Rios e corpos d’água', color: '#4c91ad', on: true },
      { name: 'Uso do solo', desc: 'Cobertura do terreno', color: '#d1a64d', on: false },
      { name: 'Limites municipais', desc: 'Divisões administrativas', color: '#71817b', on: true }
    ],
    search: '',
    selectedRegion: 'Pernambuco',
    modalOpen: false
  };

  const icon = (name, size = 18) => {
    const paths = {
      home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
      map: '<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3z"/><path d="M9 3v15M15 6v15"/>',
      layers: '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/>',
      folder: '<path d="M3 6a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M3 9h18"/>',
      database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7"/>',
      chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
      settings: '<circle cx="12" cy="12" r="3"/><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.7a8 8 0 0 1-1.6.9l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.6-.9l-1.7.7-1.4-2.4 1.4-1.1a7 7 0 0 1 0-1.9L6.1 12l1.4-2.4 1.7.7a8 8 0 0 1 1.6-.9l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.6.9l1.7-.7 1.4 2.4-1.4 1.1a7 7 0 0 1-.1 1.9z" transform="translate(-1 -1)"/>',
      search: '<circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 5 5"/>',
      folderPlus: '<path d="M3 6a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M12 10v6M9 13h6"/>',
      pin: '<path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
      compass: '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2.2 4.8-4.8 2.2 2.2-4.8z"/>',
      arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
      close: '<path d="m6 6 12 12M18 6 6 18"/>',
      plus: '<path d="M12 5v14M5 12h14"/>',
      bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
      check: '<path d="m5 12 4 4L19 6"/>',
      globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
      file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h8"/>',
      logout: '<path d="M10 17l5-5-5-5M15 12H3M21 19V5a2 2 0 0 0-2-2h-5"/>',
      eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>'
    };
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.file}</svg>`;
  };

  const brand = (small = false) => `
    <div class="brand">
      <div class="logo-mark" aria-hidden="true">
        <svg viewBox="0 0 32 32" fill="none"><path d="M16 2.8 28 9.5v13L16 29.2 4 22.5v-13L16 2.8Z" stroke="#d7fff1" stroke-width="1.6"/><path d="m16 5.8 8.8 4.9-8.8 5-8.8-5 8.8-4.9Z" fill="#b8e64d"/><path d="m7.2 10.7 8.8 5v10.1l-8.8-5V10.7Z" fill="#38c6a4"/><path d="m24.8 10.7-8.8 5v10.1l8.8-5V10.7Z" fill="#168b7b"/></svg>
      </div>
      <div><div class="brand-name">Conecta Território</div><div class="brand-sub">3D · Dados geográficos</div></div>
    </div>`;

  const topoSvg = (id = 'topo') => `
    <svg class="auth-map" viewBox="0 0 620 330" role="img" aria-label="Representação topográfica de um território">
      <defs><pattern id="${id}-grid" width="42" height="42" patternUnits="userSpaceOnUse"><path d="M42 0H0V42" fill="none" stroke="#174248" stroke-width=".8"/></pattern><linearGradient id="${id}-land" x1=".15" y1="0" x2=".8" y2="1"><stop stop-color="#4ab99d"/><stop offset="1" stop-color="#176c68"/></linearGradient></defs>
      <path d="M15 260 310 70 604 247 310 318Z" fill="url(#${id}-grid)" stroke="#17474a" stroke-width="1"/>
      <g fill="none" stroke="#1e5152" stroke-width="1.1" opacity=".75"><path d="M0 155c92-53 130-17 205-63s139-60 211-28 112 18 204-32"/><path d="M0 178c92-53 130-17 205-63s139-60 211-28 112 18 204-32"/><path d="M0 201c92-53 130-17 205-63s139-60 211-28 112 18 204-32"/></g>
      <path d="M100 182c28-28 61-27 91-55 31-29 78-46 113-27 27 15 53 12 80 0 30-14 71-9 91 17 19 24 51 36 55 60 5 28-31 48-61 53-33 6-55 30-89 26-31-4-54-19-83-10-29 9-57 7-81-8-27-17-59-15-87-24-27-8-54-14-29-32Z" fill="url(#${id}-land)" stroke="#70d6bb" stroke-width="2"/>
      <g fill="none" stroke="#b3e4cc" stroke-width="1.5" opacity=".82"><path d="M126 180c31-25 50-27 79-52 29-24 71-41 100-26 27 14 55 7 81-3 29-11 60-3 78 19 18 22 46 31 48 49 3 20-27 34-55 39-31 5-53 24-81 21-30-3-52-17-79-9-25 8-47 4-69-9-25-14-50-13-77-21-20-6-42-7-25-8Z"/><path d="M157 178c33-21 47-25 73-45 25-20 60-33 83-21 26 13 55 4 79-5 25-9 49 0 65 18 16 18 39 25 40 39 2 14-23 25-49 29-29 5-49 19-74 17-29-2-48-14-72-7-21 6-40 1-59-10-22-12-43-12-67-18-15-4-31-2-19 3Z"/><path d="M190 174c28-17 43-20 66-37 21-16 48-26 67-17 24 11 51 2 72-5 20-7 38 0 51 15 12 14 30 20 30 29 0 10-20 17-41 20-25 4-41 14-63 13-25-1-42-10-62-5-18 4-34 0-49-9-17-10-34-9-54-14-13-3-25-1-17 10Z"/></g>
      <path d="M120 216c60-42 93-42 145-18 48 22 71-53 119-40 37 10 53 42 93 13" fill="none" stroke="#d7d45c" stroke-width="2.2" stroke-dasharray="6 6" stroke-linecap="round"/>
      <circle cx="120" cy="216" r="5" fill="#dce96d"/><circle cx="477" cy="171" r="5" fill="#dce96d"/>
      <path d="M440 73c0-14 11-25 25-25s25 11 25 25c0 19-25 46-25 46S440 92 440 73Z" fill="#0c4645" stroke="#58d6b7" stroke-width="1.5"/><circle cx="465" cy="72" r="8" fill="#51d3b4"/><circle cx="465" cy="72" r="3" fill="#0a4a48"/>
      <g font-family="DM Sans, sans-serif" font-size="9"><rect x="425" y="128" width="150" height="28" rx="6" fill="#0d3337" stroke="#2a6c66"/><text x="438" y="145" fill="#d7e9e2">CAMADA DE TERRENO</text><text x="526" y="145" fill="#63d8b7">ATIVA</text></g>
      <path d="M440 164h82m-82 6h52" stroke="#317c74" stroke-width="1.4"/>
    </svg>`;

  function showToast(message) {
    toastEl.textContent = message;
    toastEl.classList.add('show');
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => toastEl.classList.remove('show'), 2800);
  }

  function authView(mode = 'login') {
    state.view = mode;
    const isSignup = mode === 'signup';
    app.innerHTML = `
      <main class="auth-page">
        <section class="auth-visual">
          ${brand()}
          <div class="auth-eyebrow"><span class="status-dot"></span> MAPAS 3D · EXPLORAÇÃO REAL</div>
          <h1>Explore o mundo<br>em outra dimensão.</h1>
          <p class="lead">Terrenos, rotas e lugares ganham vida em uma experiência geográfica tridimensional, feita para você descobrir mais.</p>
          ${topoSvg(isSignup ? 'signup' : 'login')}
          <div class="auth-features">
            <div class="feature-chip"><span class="feature-icon">${icon('map', 15)}</span><span><strong>Terrenos em 3D</strong><small>Detalhes que ganham profundidade</small></span></div>
            <div class="feature-chip"><span class="feature-icon">${icon('layers', 15)}</span><span><strong>Camadas interativas</strong><small>Navegue do panorama ao detalhe</small></span></div>
          </div>
          <div class="auth-foot">CARTOGRAFIA PARA IR MAIS LONGE</div>
        </section>
        <section class="auth-side">
          <div class="auth-top">${isSignup ? 'Já tem conta?' : ''} <button type="button" data-action="${isSignup ? 'login' : 'signup'}">${isSignup ? 'Entrar' : 'PT-BR ⌄'}</button></div>
          <div class="auth-form-wrap">
            <h2>${isSignup ? 'Crie sua conta' : 'Bem-vindo de volta'}</h2>
            <p class="form-subtitle">${isSignup ? 'Comece a explorar o mundo em 3D.' : 'Entre para continuar sua exploração.'}</p>
            <button class="google-button" type="button" data-action="google"><span class="google-g">G</span> Continuar com Google</button>
            <div class="form-divider">ou ${isSignup ? 'cadastre-se' : 'entre'} com seu e-mail</div>
            <form id="auth-form" novalidate>
              ${isSignup ? `<label class="field"><span class="field-label">Nome completo</span><input name="name" autocomplete="name" placeholder="Como podemos te chamar?" required /></label>` : ''}
              <label class="field"><span class="field-label">E-mail</span><input type="email" name="email" autocomplete="email" placeholder="voce@exemplo.com" required /></label>
              <label class="field"><span class="field-label">Senha</span><input type="password" name="password" autocomplete="${isSignup ? 'new-password' : 'current-password'}" placeholder="${isSignup ? 'Mínimo de 8 caracteres' : 'Digite sua senha'}" minlength="${isSignup ? 8 : 1}" required /></label>
              ${isSignup ? `<label class="field"><span class="field-label">Confirme sua senha</span><input type="password" name="confirm" autocomplete="new-password" placeholder="Digite a senha novamente" required /></label><label class="check-label" style="font-size:10px;color:#849391;margin:2px 0 20px"><input type="checkbox" name="terms" required> Li e aceito os Termos de uso e a Política de privacidade.</label>` : `<div class="form-options"><label class="check-label"><input type="checkbox" name="remember"> Lembrar de mim</label><button class="text-button" type="button" data-action="forgot">Esqueci minha senha</button></div>`}
              <button class="primary-button full" type="submit">${isSignup ? 'Criar minha conta' : 'Entrar no mapa'} ${icon('arrow', 16)}</button>
            </form>
            <div class="auth-bottom">${isSignup ? 'Já tem uma conta? ' : 'Primeira vez no Conecta Território 3D? ' }<button type="button" data-action="${isSignup ? 'login' : 'signup'}">${isSignup ? 'Entre para continuar sua exploração' : 'Crie sua conta'}</button></div>
            <div class="auth-privacy">Ao continuar, você concorda com nossos Termos de uso e Política de privacidade.</div>
          </div>
        </section>
      </main>`;
  }

  const navItems = [
    ['dashboard', 'home', 'Visão geral'], ['explore', 'map', 'Explorar mapa'], ['layers', 'layers', 'Camadas'],
    ['projects', 'folder', 'Projetos'], ['data', 'database', 'Dados territoriais'], ['reports', 'chart', 'Relatórios'], ['settings', 'settings', 'Configurações']
  ];
  const pageNames = { dashboard: 'Visão geral', explore: 'Explorar mapa', layers: 'Camadas', projects: 'Projetos', data: 'Dados territoriais', reports: 'Relatórios', settings: 'Configurações' };

  function shell(content) {
    const current = state.view;
    app.innerHTML = `
      <div class="app-shell">
        <aside class="sidebar">
          ${brand()}
          <nav class="nav-list" aria-label="Navegação principal">
            ${navItems.map(([key, ico, label]) => `<button type="button" class="nav-item ${current === key ? 'active' : ''}" data-view="${key}"><span class="nav-icon">${icon(ico)}</span><span>${label}</span></button>`).join('')}
          </nav>
          <div class="sidebar-help"><strong>Precisa de ajuda?</strong><span>Acesse a documentação<br>e os tutoriais do sistema.</span></div>
        </aside>
        <main class="main-area">
          <header class="topbar">
            <div class="breadcrumb">Início&nbsp; / &nbsp;<b>${pageNames[current] || 'Visão geral'}</b></div>
            <div class="top-actions">
              <label class="global-search">${icon('search')}<input id="global-search" type="search" placeholder="Buscar território, camada ou projeto..." value="${escapeHtml(state.search)}" /></label>
              <button class="inline-link" type="button" aria-label="Notificações" data-action="notifications">${icon('bell')}</button>
              <div class="profile"><span class="avatar">${initials(state.user?.name || 'Clécio')}</span>${escapeHtml(state.user?.name || 'Clécio')}</div>
              <button class="inline-link" type="button" aria-label="Sair" title="Sair" data-action="logout">${icon('logout')}</button>
            </div>
          </header>
          <div class="page-content">${content}</div>
        </main>
      </div>
      ${state.modalOpen ? projectModal() : ''}`;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function initials(name) { return name.split(/\s+/).filter(Boolean).slice(0, 2).map(x => x[0].toUpperCase()).join('') || 'CT'; }
  function heading(title, desc, action = '') {
    return `<div class="page-heading"><div><h1>${title}</h1><p>${desc}</p></div>${action}</div>`;
  }
  function statCard(label, value, detail, ico) {
    return `<article class="stat-card"><span class="stat-label">${label}</span><div class="stat-value">${value}</div><div class="stat-detail">${detail}</div><span class="stat-icon">${icon(ico)}</span></article>`;
  }

  function terrainMap(id, compact = false) {
    return `<svg viewBox="0 0 760 390" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Mapa topográfico ilustrativo">
      <defs><pattern id="${id}-grid" width="42" height="42" patternUnits="userSpaceOnUse"><path d="M42 0H0V42" fill="none" stroke="#d6e3dc" stroke-width=".8"/></pattern><linearGradient id="${id}-area" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#b5d9c3"/><stop offset="1" stop-color="#d3e6d9"/></linearGradient></defs>
      <rect width="760" height="390" fill="#eaf1ed"/><rect width="760" height="390" fill="url(#${id}-grid)"/>
      <path d="M-20 82c88-25 120 35 207 4s132-28 205 0 126 18 190-14 107-29 196 6M-20 103c88-25 120 35 207 4s132-28 205 0 126 18 190-14 107-29 196 6" fill="none" stroke="#d0dfd7" stroke-width="1.4"/>
      <path d="M62 202c26-26 60-25 92-49 37-27 77-58 120-45 34 10 57 12 88-2 33-15 77-9 98 18 23 30 57 32 64 62 6 28-32 50-67 55-41 5-68 31-105 28-32-3-57-20-90-9-32 10-60 5-88-10-33-18-72-13-102-26-27-12-42-10-10-22Z" fill="url(#${id}-area)" stroke="#82b69b" stroke-width="2"/>
      <g fill="none" stroke="#6da88b" stroke-width="1.5" opacity=".9"><path d="M95 197c37-23 51-23 81-43 34-24 68-43 101-32 32 10 58 9 85-2 31-12 66-4 87 19 21 24 48 28 53 49 5 19-27 36-59 39-36 4-64 24-96 22-31-2-54-16-82-7-27 8-50 3-73-9-28-14-60-12-86-22-22-8-30-7-11-14Z"/><path d="M132 194c35-20 48-20 76-37 29-19 58-32 87-23 28 9 53 5 77-4 27-9 54-2 71 17 17 18 39 23 43 39 4 14-23 26-49 29-32 4-55 18-83 17-27-2-48-12-72-5-22 6-42 2-61-8-24-12-51-11-73-18-17-5-28-3-16-7Z"/><path d="M172 192c28-15 43-16 67-29 25-14 48-23 71-16 23 7 47 2 67-4 20-6 42 0 55 14 13 13 30 18 33 29 2 10-18 19-41 21-26 3-46 13-69 12-23-1-40-9-61-4-18 4-34 1-49-7-19-10-41-9-59-14-13-4-25-3-14-2Z"/></g>
      <path d="M74 282c68-25 111-13 166-31 58-19 87 5 144-7 49-11 89-33 147-18 53 14 87-5 155-33" fill="none" stroke="#70a8bb" stroke-width="3" stroke-linecap="round"/>
      <path d="M118 247c54-35 89-42 135-23 47 18 76-45 125-38 47 6 65 44 112 15" fill="none" stroke="#d2bd62" stroke-width="2" stroke-dasharray="7 6" stroke-linecap="round"/>
      <circle cx="118" cy="247" r="5" fill="#c5b64f"/><circle cx="490" cy="201" r="5" fill="#c5b64f"/>
      ${compact ? '<circle cx="520" cy="134" r="7" fill="#168c75" stroke="#fff" stroke-width="3"/>' : '<path d="M487 91c0-13 10-23 23-23s23 10 23 23c0 17-23 42-23 42s-23-25-23-42Z" fill="#168c75" stroke="#fff" stroke-width="2"/><circle cx="510" cy="91" r="6" fill="#d9fff2"/>'}
      <g fill="none" stroke="#bfd2c8" stroke-width="1"><path d="M0 330c110-23 172 17 269-3s154 15 260-6 146 0 231-16"/><path d="M0 351c110-23 172 17 269-3s154 15 260-6 146 0 231-16"/></g>
    </svg>`;
  }

  function projectRow(project, index) {
    const color = project.type === 'H₂O' ? 'blue' : project.type === 'GIS' ? 'gold' : '';
    return `<div class="project-row"><div class="project-thumb ${color}">${escapeHtml(project.type)}</div><div class="project-info"><strong>${escapeHtml(project.name)}</strong><small>${escapeHtml(project.place)} · ${escapeHtml(project.updated)}</small></div></div>`;
  }

  function dashboardView() {
    const filtered = state.projects.filter(p => `${p.name} ${p.place}`.toLowerCase().includes(state.search.toLowerCase()));
    return `${heading('Visão geral', 'Acompanhe seus territórios e dados em um só lugar.', `<button class="primary-button" data-action="new-project">${icon('plus')} Novo projeto</button>`)}
      <section class="stats-grid">
        ${statCard('Projetos ativos', String(state.projects.length).padStart(2, '0'), 'Seus trabalhos territoriais', 'folder')}
        ${statCard('Camadas disponíveis', '12', 'Em 3 categorias', 'layers')}
        ${statCard('Territórios salvos', '08', 'Seus locais favoritos', 'pin')}
      </section>
      <section class="dashboard-grid">
        <article class="panel"><div class="panel-head"><div><h2>Mapa do território</h2><p>Visualização de relevo e limites geográficos</p></div><button class="inline-link" data-view="explore">Abrir mapa ${icon('arrow', 13)}</button></div><div class="map-preview">${terrainMap('dashboard-map', true)}<span class="map-caption">${icon('pin', 11)} &nbsp; Área selecionada · Pernambuco</span></div></article>
        <article class="panel"><div class="panel-head"><div><h2>Projetos recentes</h2><p>Atividade dos seus projetos</p></div><button class="inline-link" data-view="projects">Ver todos →</button></div><div class="project-list">${filtered.slice(0, 4).map(projectRow).join('') || '<div class="empty-state">Nenhum projeto encontrado.</div>'}</div></article>
      </section>
      <article class="panel quick-panel"><div class="panel-head"><h2>Acesso rápido</h2></div><div class="quick-grid">
        <button class="quick-link" data-view="explore"><span class="quick-icon">${icon('map')}</span><span><strong>Explorar mapa</strong><small>Consulte os dados no mapa</small></span></button>
        <button class="quick-link" data-view="layers"><span class="quick-icon">${icon('layers')}</span><span><strong>Gerenciar camadas</strong><small>Ative e organize camadas</small></span></button>
        <button class="quick-link" data-action="new-project"><span class="quick-icon">${icon('folderPlus')}</span><span><strong>Criar projeto</strong><small>Comece uma nova análise</small></span></button>
      </div></article>`;
  }

  function layerRows() {
    return state.layers.map((layer, i) => `<div class="layer-row"><span class="layer-swatch" style="background:${layer.color}"></span><span class="layer-copy"><strong>${escapeHtml(layer.name)}</strong><small>${escapeHtml(layer.desc)}</small></span><button class="toggle ${layer.on ? 'on' : ''}" role="switch" aria-checked="${layer.on}" aria-label="Ativar ${escapeHtml(layer.name)}" data-layer="${i}"></button></div>`).join('');
  }

  function exploreView() {
    return `${heading('Explorar mapa', 'Pesquise uma região e escolha as camadas que deseja visualizar.')}
      <div class="explore-top"><label class="explore-search">${icon('search')}<input id="region-search" placeholder="Buscar município, endereço ou coordenadas" value="${escapeHtml(state.selectedRegion)}" /></label><button class="primary-button" data-action="search-region">Pesquisar ${icon('arrow', 15)}</button></div>
      <div class="explore-layout">
        <article class="panel map-workspace"><div class="panel-head"><div><h2>Mapa interativo</h2><p>Área selecionada · ${escapeHtml(state.selectedRegion)}, Brasil</p></div><button class="inline-link" data-action="fullscreen-map">Expandir ${icon('compass', 14)}</button></div>
          <div class="map-large">${terrainMap('explore-map')}<div class="map-tools"><button data-action="zoom-in" aria-label="Aumentar zoom">+</button><button data-action="zoom-out" aria-label="Diminuir zoom">−</button><button data-action="center-map" aria-label="Centralizar mapa">${icon('compass', 16)}</button></div><div class="map-legend"><div class="legend-item"><span class="legend-dot" style="background:#279a7b"></span> Elevação</div><div class="legend-item"><span class="legend-dot" style="background:#4c91ad"></span> Hidrografia</div><div class="legend-item"><span class="legend-dot" style="background:#d1a64d"></span> Uso do solo</div></div><span class="map-coordinates">-8.0476, -34.8770</span></div>
        </article>
        <aside class="side-stack"><article class="panel"><div class="panel-head"><div><h2>Camadas</h2><p>Selecione o que aparece no mapa</p></div><button class="inline-link" data-view="layers">Gerenciar</button></div><div class="layer-list">${layerRows()}</div></article>
          <article class="panel"><div class="panel-head"><h2>Área selecionada</h2></div><div class="region-details"><div><small>Território</small><strong>${escapeHtml(state.selectedRegion)}</strong></div><div><small>Região</small><strong>Brasil · Nordeste</strong></div><div><small>Coordenadas</small><strong>-8.0476, -34.8770</strong></div><button class="primary-button full" data-action="save-region">Salvar território</button></div></article>
        </aside>
      </div>`;
  }

  function projectsView() {
    const rows = state.projects.filter(p => `${p.name} ${p.place}`.toLowerCase().includes(state.search.toLowerCase()));
    return `${heading('Projetos', 'Organize seus estudos, mapas e análises territoriais.', `<button class="primary-button" data-action="new-project">${icon('plus')} Novo projeto</button>`)}
      <div class="toolbar"><input id="page-search" type="search" placeholder="Pesquisar projeto..." value="${escapeHtml(state.search)}"><button class="inline-link" data-action="clear-search">Limpar filtros</button></div>
      <article class="panel table-wrap"><table><thead><tr><th>Projeto</th><th>Localização</th><th>Última atualização</th><th>Status</th><th>Tipo</th></tr></thead><tbody>${rows.map(p => `<tr><td><strong>${escapeHtml(p.name)}</strong></td><td>${escapeHtml(p.place)}</td><td>${escapeHtml(p.updated)}</td><td><span class="status ${p.status === 'Concluído' ? 'gray' : ''}">${escapeHtml(p.status)}</span></td><td>${escapeHtml(p.type)}</td></tr>`).join('')}</tbody></table>${rows.length ? '' : '<div class="empty-state">Nenhum projeto corresponde à pesquisa.</div>'}</article>`;
  }

  function layersView() {
    return `${heading('Camadas', 'Controle as informações que compõem a visualização territorial.')}
      <div class="explore-layout"><article class="panel"><div class="panel-head"><div><h2>Biblioteca de camadas</h2><p>Ative ou desative as informações disponíveis</p></div><button class="inline-link" data-action="reset-layers">Restaurar padrão</button></div><div class="layer-list">${layerRows()}</div></article><article class="panel"><div class="panel-head"><h2>Sobre as camadas</h2></div><p style="font-size:11px;line-height:1.7;color:#849391">As camadas permitem visualizar diferentes conjuntos de informações sobre uma mesma região. Você pode combinar elevação, hidrografia, cobertura do solo e limites administrativos.</p><div class="region-details"><div><small>Camadas ativas</small><strong>${state.layers.filter(l => l.on).length} de ${state.layers.length}</strong></div><button class="primary-button full" data-view="explore">Visualizar no mapa ${icon('arrow', 14)}</button></div></article></div>`;
  }

  function dataView() {
    const entries = [['Modelo digital de elevação', 'Relevo', 'GeoTIFF', 'Disponível'], ['Rede hidrográfica', 'Hidrografia', 'Shapefile', 'Disponível'], ['Uso e cobertura do solo', 'Ambiental', 'GeoJSON', 'Em atualização'], ['Limites municipais', 'Administrativo', 'Shapefile', 'Disponível']];
    return `${heading('Dados territoriais', 'Consulte os conjuntos de dados disponíveis para suas análises.')}
      <div class="stats-grid">${statCard('Conjuntos de dados','12','Fontes cadastradas','database')}${statCard('Categorias','03','Temas de informação','layers')}${statCard('Última atualização','Hoje','Dados demonstrativos','chart')}</div>
      <article class="panel table-wrap"><div class="panel-head"><div><h2>Catálogo de dados</h2><p>Fontes disponíveis no ambiente</p></div></div><table><thead><tr><th>Conjunto de dados</th><th>Categoria</th><th>Formato</th><th>Situação</th></tr></thead><tbody>${entries.map(r=>`<tr><td><strong>${r[0]}</strong></td><td>${r[1]}</td><td>${r[2]}</td><td><span class="status ${r[3] === 'Disponível' ? '' : 'gray'}">${r[3]}</span></td></tr>`).join('')}</tbody></table></article>`;
  }

  function reportsView() {
    return `${heading('Relatórios', 'Acompanhe os resultados e a atividade dos seus territórios.')}
      <div class="stats-grid">${statCard('Projetos analisados',String(state.projects.length).padStart(2,'0'),'No espaço de trabalho','folder')}${statCard('Camadas utilizadas',String(state.layers.filter(l=>l.on).length).padStart(2,'0'),'Ativas no momento','layers')}${statCard('Território em foco','PE','Pernambuco · Brasil','pin')}</div>
      <div class="dashboard-grid"><article class="panel"><div class="panel-head"><div><h2>Resumo do espaço de trabalho</h2><p>Indicadores demonstrativos</p></div></div><div style="display:grid;gap:17px;padding:16px 4px 8px">${[['Projetos com atividade',state.projects.length,4],['Camadas habilitadas',state.layers.filter(l=>l.on).length,4],['Categorias de dados',3,4]].map(([l,v,max])=>`<div><div style="display:flex;justify-content:space-between;font-size:10px;margin-bottom:7px"><strong>${l}</strong><span style="color:#879694">${v}</span></div><div style="height:8px;background:#edf2ef;border-radius:20px;overflow:hidden"><div style="height:100%;width:${v/max*100}%;background:#39b99b;border-radius:20px"></div></div></div>`).join('')}</div></article><article class="panel"><div class="panel-head"><h2>Exportação</h2></div><p style="font-size:11px;color:#879492;line-height:1.65">A geração de relatórios em PDF e a exportação de dados estarão disponíveis quando o backend estiver conectado.</p><button class="primary-button full" data-action="report-demo">Solicitar relatório ${icon('file',14)}</button></article></div>`;
  }

  function settingsView() {
    return `${heading('Configurações', 'Gerencie suas preferências de acesso e visualização.')}
      <article class="panel" style="max-width:720px"><div class="panel-head"><div><h2>Perfil</h2><p>Informações da conta atualmente conectada</p></div></div><div class="field"><span class="field-label">Nome</span><input value="${escapeHtml(state.user?.name || 'Clécio')}" disabled></div><div class="field"><span class="field-label">E-mail</span><input value="${escapeHtml(state.user?.email || 'usuario@exemplo.com')}" disabled></div><div class="form-options" style="justify-content:flex-start">${icon('check', 14)} Sessão local de demonstração</div><button class="primary-button" data-action="logout">Sair da conta ${icon('logout', 14)}</button></article>`;
  }

  function projectModal() {
    return `<div class="modal-backdrop" data-action="close-modal"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div class="modal-head"><h2 id="modal-title">Novo projeto</h2><button class="close-button" data-action="close-modal" aria-label="Fechar">×</button></div><form id="project-form"><label class="field"><span class="field-label">Nome do projeto</span><input name="name" placeholder="Ex.: Mapeamento de área urbana" required maxlength="80"></label><label class="field"><span class="field-label">Localização</span><input name="place" placeholder="Ex.: Recife · PE" required maxlength="80"></label><label class="field"><span class="field-label">Tipo de projeto</span><input name="type" placeholder="Ex.: MAP, GIS ou H₂O" maxlength="12" value="MAP"></label><button class="primary-button full" type="submit">Criar projeto ${icon('arrow', 14)}</button></form></section></div>`;
  }

  function render() {
    if (state.view === 'login' || state.view === 'signup') return authView(state.view);
    const content = ({ dashboard: dashboardView, explore: exploreView, projects: projectsView, layers: layersView, data: dataView, reports: reportsView, settings: settingsView }[state.view] || dashboardView)();
    shell(content);
  }

  function enterApp(user) {
    state.user = user;
    state.view = 'dashboard';
    render();
    showToast(`Bem-vindo${user.name ? ', ' + user.name.split(' ')[0] : ''}!`);
  }

  app.addEventListener('submit', (event) => {
    if (event.target.id === 'auth-form') {
      event.preventDefault();
      const form = new FormData(event.target);
      const email = String(form.get('email') || '').trim();
      const password = String(form.get('password') || '');
      if (!email || !/^\S+@\S+\.\S+$/.test(email)) return showToast('Informe um e-mail válido.');
      if (password.length < (state.view === 'signup' ? 8 : 1)) return showToast(state.view === 'signup' ? 'A senha precisa ter pelo menos 8 caracteres.' : 'Informe sua senha.');
      if (state.view === 'signup') {
        const name = String(form.get('name') || '').trim();
        if (!name) return showToast('Informe seu nome completo.');
        if (password !== String(form.get('confirm') || '')) return showToast('As senhas não coincidem.');
        if (!form.get('terms')) return showToast('Aceite os termos para continuar.');
        const user = { name, email };
        localStorage.setItem('conecta-demo-user', JSON.stringify(user));
        enterApp(user);
      } else {
        const saved = localStorage.getItem('conecta-demo-user');
        let user = { name: email.split('@')[0], email };
        if (saved) {
          try { const previous = JSON.parse(saved); if (previous.email === email) user = previous; } catch (_) {}
        }
        if (form.get('remember')) localStorage.setItem('conecta-demo-user', JSON.stringify(user));
        enterApp(user);
      }
    }
    if (event.target.id === 'project-form') {
      event.preventDefault();
      const form = new FormData(event.target);
      const name = String(form.get('name') || '').trim();
      const place = String(form.get('place') || '').trim();
      if (!name || !place) return showToast('Preencha o nome e a localização.');
      state.projects.unshift({ name, place, updated: 'Criado agora', type: String(form.get('type') || 'MAP').trim().toUpperCase(), status: 'Em andamento' });
      state.modalOpen = false;
      state.view = 'projects';
      render();
      showToast('Projeto criado nesta demonstração.');
    }
  });

  app.addEventListener('click', (event) => {
    const viewButton = event.target.closest('[data-view]');
    if (viewButton) {
      state.view = viewButton.dataset.view;
      state.search = '';
      render();
      return;
    }
    const actionButton = event.target.closest('[data-action]');
    if (actionButton) {
      const action = actionButton.dataset.action;
      if (action === 'login' || action === 'signup') return authView(action);
      if (action === 'google') return showToast('Login Google será habilitado após configurar o serviço de autenticação.');
      if (action === 'forgot') return showToast('A recuperação de senha depende do serviço de autenticação.');
      if (action === 'logout') { state.user = null; state.view = 'login'; state.search = ''; return authView('login'); }
      if (action === 'notifications') return showToast('Você não tem notificações novas.');
      if (action === 'new-project') { state.modalOpen = true; return render(); }
      if (action === 'close-modal') { if (event.target.classList.contains('modal-backdrop') || actionButton.classList.contains('close-button')) { state.modalOpen = false; render(); } return; }
      if (action === 'search-region') {
        const input = document.getElementById('region-search');
        const value = input?.value.trim();
        if (!value) return showToast('Digite um município, endereço ou coordenadas.');
        state.selectedRegion = value;
        render();
        return showToast(`Região selecionada: ${value}.`);
      }
      if (action === 'save-region') return showToast(`${state.selectedRegion} foi adicionado aos territórios salvos (demonstração).`);
      if (action === 'reset-layers') { state.layers.forEach((l, i) => l.on = [true, true, false, true][i]); render(); return showToast('Camadas restauradas.'); }
      if (action === 'clear-search') { state.search = ''; render(); return; }
      if (action === 'zoom-in' || action === 'zoom-out') return showToast(action === 'zoom-in' ? 'Zoom aumentado (visualização demonstrativa).' : 'Zoom reduzido (visualização demonstrativa).');
      if (action === 'center-map') return showToast('Mapa centralizado na região selecionada.');
      if (action === 'fullscreen-map') return showToast('A visualização em tela cheia será conectada ao mapa interativo.');
      if (action === 'report-demo') return showToast('A exportação será habilitada quando o backend estiver conectado.');
    }
    const layerButton = event.target.closest('[data-layer]');
    if (layerButton) {
      const layer = state.layers[Number(layerButton.dataset.layer)];
      if (layer) { layer.on = !layer.on; render(); }
    }
  });

  app.addEventListener('input', (event) => {
    if (event.target.id === 'global-search' || event.target.id === 'page-search') {
      const value = event.target.value;
      state.search = value;
      const position = event.target.id === 'global-search' ? 'global' : 'page';
      if (state.view === 'dashboard' || state.view === 'projects') {
        const selectionStart = event.target.selectionStart;
        render();
        const target = document.getElementById(position === 'global' ? 'global-search' : 'page-search');
        if (target) { target.focus(); target.setSelectionRange(selectionStart, selectionStart); }
      }
    }
  });

  render();
})();
