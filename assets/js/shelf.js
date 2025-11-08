(function initBookshelf() {
  const shelfList = document.getElementById('bookshelf');
  const infoPanel = document.getElementById('info-panel');
  const infoCover = document.getElementById('info-cover');
  const infoTitle = document.getElementById('info-title');
  const infoMeta = document.getElementById('info-meta');
  const infoDescription = document.getElementById('info-description');
  const infoTags = document.getElementById('info-tags');
  const infoButton = document.getElementById('info-button');
  const emptyState = document.getElementById('empty-state');
  const statTotal = document.getElementById('stat-total');
  const searchInput = document.getElementById('search-input');
  const pillFilters = document.querySelectorAll('.pill');
  const viewToggleButtons = document.querySelectorAll('.view-toggle__btn');

  if (!shelfList) return;

  let books = [];
  let filteredBooks = [];
  let currentActiveCard = null;
  let currentFilter = 'all';
  let currentView = 'grid';

  fetch('data/books.json', { cache: 'no-cache' })
    .then((res) => res.json())
    .then((payload) => {
      books = Array.isArray(payload) ? payload : payload.books || [];
      if (!books.length) {
        showEmpty('아직 책이 없습니다.', 'PDF를 업로드해 첫 번째 AI 프레젠테이션을 만들어 보세요.');
        updateStat(0);
        return;
      }
      updateStat(books.length);
      filteredBooks = [...books];
      renderBooks(filteredBooks);
      bindKeyboardShortcut();
    })
    .catch((error) => {
      console.error(error);
      showEmpty('책 데이터를 불러오는 데 실패했습니다.', 'data/books.json 파일을 확인해 주세요.');
      updateStat(0);
    });

  function updateStat(count) {
    if (statTotal) {
      statTotal.textContent = count.toString();
    }
  }

  function normalize(str) {
    return (str || '').toString().toLowerCase();
  }

  function applyFilters() {
    const keyword = normalize(searchInput ? searchInput.value : '');
    filteredBooks = books.filter((book) => {
      const inFilter =
        currentFilter === 'all' ||
        (Array.isArray(book.tags) &&
          book.tags.some((t) => normalize(t).includes(currentFilter)));
      if (!inFilter) return false;

      if (!keyword) return true;

      const haystack = [
        book.title,
        book.author,
        book.description,
        ...(Array.isArray(book.tags) ? book.tags : []),
      ]
        .map(normalize)
        .join(' ');

      return haystack.includes(keyword);
    });

    if (!filteredBooks.length) {
      if (shelfList) shelfList.innerHTML = '';
      showEmpty(
        '검색 조건에 맞는 프레젠테이션이 없습니다.',
        '필터를 초기화하거나 다른 키워드를 입력해 보세요.'
      );
      clearInfoPanel();
      return;
    }

    hideEmpty();
    renderBooks(filteredBooks);
  }

  function showEmpty(title, sub) {
    if (!emptyState) return;
    emptyState.hidden = false;
    emptyState.querySelector('p') && (emptyState.querySelector('p').textContent = title);
    const subEl = emptyState.querySelector('.empty-sub');
    if (subEl) subEl.textContent = sub || '';
  }

  function hideEmpty() {
    if (!emptyState) return;
    emptyState.hidden = true;
  }

  function renderBooks(list) {
    if (!shelfList) return;

    const fragment = document.createDocumentFragment();
    currentActiveCard = null;

    list.forEach((book, index) => {
      const card = document.createElement('article');
      card.className = 'book-card';
      card.setAttribute('role', 'button');
      card.setAttribute('tabindex', '0');
      card.setAttribute('aria-label', `${book.title || '책'} 프레젠테이션 열기`);

      const coverWrap = document.createElement('div');
      coverWrap.className = 'book-card__cover-wrap';

      const cover = document.createElement('div');
      cover.className = 'book-card__cover';

      const img = document.createElement('img');
      img.src = book.cover || 'assets/covers/default.svg';
      img.alt = book.title ? `${book.title} 표지` : '책 표지';
      img.loading = 'lazy';

      cover.appendChild(img);
      coverWrap.appendChild(cover);

      const meta = document.createElement('div');
      meta.className = 'book-card__meta';

      const titleEl = document.createElement('div');
      titleEl.className = 'book-card__title';
      titleEl.textContent = book.title || '제목 미상';

      const subtitleEl = document.createElement('div');
      subtitleEl.className = 'book-card__subtitle';
      const metaBits = [];
      if (book.author) metaBits.push(book.author);
      if (book.date) metaBits.push(book.date);
      subtitleEl.textContent = metaBits.join(' · ');

      meta.appendChild(titleEl);
      if (metaBits.length) meta.appendChild(subtitleEl);

      card.appendChild(coverWrap);
      card.appendChild(meta);

      const activate = () => {
        if (currentActiveCard && currentActiveCard !== card) {
          currentActiveCard.classList.remove('is-active');
        }
        currentActiveCard = card;
        card.classList.add('is-active');
        updateInfoPanel(book);
      };

      const openPresentation = () => {
        if (book.presentation) {
          const url = book.presentation.startsWith('http')
            ? book.presentation
            : `${book.presentation}`;
          window.open(url, '_blank', 'noopener');
        }
      };

      card.addEventListener('mouseenter', activate);
      card.addEventListener('focus', activate);
      card.addEventListener('click', openPresentation);
      card.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          openPresentation();
        }
      });

      if (index === 0) {
        // pre-select first card
        card.classList.add('is-active');
        updateInfoPanel(book);
        currentActiveCard = card;
      }

      fragment.appendChild(card);
    });

    shelfList.innerHTML = '';
    shelfList.appendChild(fragment);

    applyViewMode(); // ensure latest view mode is reflected
  }

  function updateInfoPanel(book) {
    if (!infoPanel || !book) return;

    const cover = book.cover || 'assets/covers/default.svg';
    if (infoCover) {
      infoCover.src = cover;
      infoCover.alt = book.title ? `${book.title} 표지` : '책 표지';
    }

    if (infoTitle) {
      infoTitle.textContent = book.title || '제목 미상';
    }

    if (infoMeta) {
      const bits = [];
      if (book.author) bits.push(book.author);
      if (book.date) bits.push(book.date);
      infoMeta.textContent = bits.length
        ? bits.join(' · ')
        : 'AI가 생성한 슬라이드, PDF 기반 요약';
    }

    if (infoDescription) {
      infoDescription.textContent = book.description || '';
      infoDescription.style.display = book.description ? 'block' : 'none';
    }

    if (infoTags) {
      infoTags.innerHTML = '';
      if (Array.isArray(book.tags) && book.tags.length) {
        book.tags.forEach((tag) => {
          const chip = document.createElement('span');
          chip.textContent = `#${tag}`;
          infoTags.appendChild(chip);
        });
      }
    }

    if (infoButton) {
      if (book.presentation) {
        const href = book.presentation.startsWith('http')
          ? book.presentation
          : `${book.presentation}`;
        infoButton.href = href;
        infoButton.target = '_blank';
      } else {
        infoButton.href = '#';
        infoButton.removeAttribute('target');
      }
    }
  }

  function clearInfoPanel() {
    if (!infoPanel) return;
    if (infoTitle) {
      infoTitle.textContent = '책을 선택해 상세 정보를 확인하세요';
    }
    if (infoMeta) {
      infoMeta.textContent = 'AI가 생성한 슬라이드, PDF 기반 요약';
    }
    if (infoDescription) {
      infoDescription.textContent = '';
      infoDescription.style.display = 'none';
    }
    if (infoTags) {
      infoTags.innerHTML = '';
    }
    if (infoCover) {
      infoCover.src = 'assets/covers/default.svg';
      infoCover.alt = '책 표지';
    }
    if (infoButton) {
      infoButton.href = '#';
      infoButton.removeAttribute('target');
    }
  }

  // Search
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      applyFilters();
    });

    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        searchInput.value = '';
        applyFilters();
        searchInput.blur();
      }
    });
  }

  // "/" focus shortcut
  function bindKeyboardShortcut() {
    document.addEventListener('keydown', (e) => {
      if (e.key === '/' && !isTypingInInput(e.target)) {
        e.preventDefault();
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }
    });
  }

  function isTypingInInput(target) {
    if (!target) return false;
    const tag = target.tagName;
    return tag === 'INPUT' || tag === 'TEXTAREA' || target.isContentEditable;
  }

  // Filter pills: disable fixed category behavior, always show all for simplicity
  pillFilters.forEach((pill) => {
    pill.addEventListener('click', () => {
      currentFilter = 'all';
      pillFilters.forEach((p) => p.classList.toggle('is-active', p === pill));
      applyFilters();
    });
  });

  // View toggle
  viewToggleButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const view = btn.getAttribute('data-view') || 'grid';
      if (view === currentView) return;
      currentView = view;
      viewToggleButtons.forEach((b) => {
        const isActive = b === btn;
        b.classList.toggle('is-active', isActive);
        b.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      });
      applyViewMode();
    });
  });

  function applyViewMode() {
    if (!shelfList) return;
    if (currentView === 'stack') {
      shelfList.classList.add('view-stack');
      Array.from(shelfList.children).forEach((card, index) => {
        if (!(card instanceof HTMLElement)) return;
        const offset = index % 5;
        card.style.transform = `translateY(${offset * 2}px) translateX(${offset *
          2}px) rotate(${(offset - 2) * 0.6}deg)`;
      });
    } else {
      shelfList.classList.remove('view-stack');
      Array.from(shelfList.children).forEach((card) => {
        if (card instanceof HTMLElement) {
          card.style.transform = '';
        }
      });
    }
  }
})();
