(function initBookshelf() {
  const shelfStack = document.getElementById('bookshelf');
  const stackWrapper = document.querySelector('.shelf-stack');
  const parallax = document.querySelector('.parallax');
  const infoPanel = document.getElementById('info-panel');
  const infoCover = document.getElementById('info-cover');
  const infoTitle = document.getElementById('info-title');
  const infoMeta = document.getElementById('info-meta');
  const infoDescription = document.getElementById('info-description');
  const infoTags = document.getElementById('info-tags');
  const infoButton = document.getElementById('info-button');
  const emptyState = document.getElementById('empty-state');

  if (!shelfStack) {
    return;
  }

  let currentActiveCard = null;

  const mobileQuery = window.matchMedia('(max-width: 768px)');
  let motionInitialized = false;

  const handleMobileChange = (event) => {
    document.body.classList.toggle('is-mobile', event.matches);
    if (!event.matches && !motionInitialized) {
      setupMotion();
    }
  };

  handleMobileChange(mobileQuery);
  mobileQuery.addEventListener('change', handleMobileChange);

  fetch('data/books.json', { cache: 'no-cache' })
    .then((res) => res.json())
    .then((payload) => {
      const books = Array.isArray(payload) ? payload : payload.books || [];
      if (!books.length) {
        if (emptyState) {
          emptyState.style.display = 'flex';
          emptyState.innerHTML = '<div><strong>아직 책이 없습니다.</strong><br>PDF를 업로드해 첫 번째 책을 등록해 보세요.</div>';
        }
        return;
      }
      if (emptyState) {
        emptyState.style.display = 'none';
      }
      renderBooks(books);
      setupMotion();
    })
    .catch((error) => {
      console.error(error);
      if (emptyState) {
        emptyState.style.display = 'flex';
        emptyState.textContent = '책 데이터를 불러오는 데 실패했습니다.';
      }
    });

  function renderBooks(books) {
    const fragment = document.createDocumentFragment();
    const perRow = books.length <= 3 ? books.length : books.length <= 6 ? 3 : 4;
    const rows = [];
    books.forEach((book, index) => {
      if (index % perRow === 0) {
        rows.push([]);
      }
      rows[rows.length - 1].push(book);
    });

    rows.forEach((rowBooks, rowIndex) => {
      const row = document.createElement('div');
      row.className = 'shelf-row';
      const depth = (rows.length - rowIndex - 1) * 55;
      row.style.setProperty('--depth', `${depth}px`);

      rowBooks.forEach((book, cardIndex) => {
        const card = document.createElement('article');
        card.className = 'book-card';
        const depthOffset = (rows.length - rowIndex - 1) * 8 + (cardIndex % 2 === 0 ? 0 : 10);
        card.style.setProperty('--depth-offset', `${depthOffset}px`);
        card.style.setProperty('--twist', `${randomRange(-3, 3)}deg`);
        card.style.setProperty('--yaw', `${randomRange(-4, 4)}deg`);
        card.style.animationDelay = `${(rowIndex * 0.45 + cardIndex * 0.18).toFixed(2)}s`;
        card.setAttribute('role', 'button');
        card.setAttribute('tabindex', '0');
        card.setAttribute('aria-label', `${book.title || '책'} 보기`);

        const body = document.createElement('div');
        body.className = 'book-card__body';

        const cover = document.createElement('div');
        cover.className = 'book-card__cover';
        const img = document.createElement('img');
        img.src = book.cover || 'assets/covers/default.svg';
        img.alt = book.title ? `${book.title} 표지` : '책 표지';
        img.loading = 'lazy';
        cover.appendChild(img);

        const back = document.createElement('div');
        back.className = 'book-card__back';

        const topEdge = document.createElement('div');
        topEdge.className = 'book-card__top';

        const bottomEdge = document.createElement('div');
        bottomEdge.className = 'book-card__bottom';

        const edge = document.createElement('div');
        edge.className = 'book-card__edge';

        const shine = document.createElement('div');
        shine.className = 'book-card__shine';

        card.append(body, cover, back, topEdge, bottomEdge, edge, shine);

        const activate = () => {
          if (currentActiveCard && currentActiveCard !== card) {
            currentActiveCard.classList.remove('is-active');
          }
          currentActiveCard = card;
          card.classList.add('is-active');
        };

        const showInfo = () => {
          activate();
          updateInfoPanel(book);
        };
        const openPresentation = () => {
          if (book.presentation) {
            const url = book.presentation.startsWith('http') ? book.presentation : `${book.presentation}`;
            window.open(url, '_blank');
          }
        };

        card.addEventListener('mouseenter', showInfo);
        card.addEventListener('focus', showInfo);
        card.addEventListener('touchstart', showInfo, { passive: true });
        card.addEventListener('click', openPresentation);
        card.addEventListener('keydown', (event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            openPresentation();
          }
        });

        row.appendChild(card);
      });

      fragment.appendChild(row);
    });

    shelfStack.innerHTML = '';
    shelfStack.appendChild(fragment);

    const firstCard = shelfStack.querySelector('.book-card');
    if (firstCard && books[0]) {
      currentActiveCard = firstCard;
      currentActiveCard.classList.add('is-active');
      updateInfoPanel(books[0]);
    }

  }

  function updateInfoPanel(book) {
    if (!infoPanel) return;
    if (!book) {
      if (currentActiveCard) {
        currentActiveCard.classList.remove('is-active');
        currentActiveCard = null;
      }
      infoPanel.classList.remove('visible');
      return;
    }
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
      infoMeta.textContent = bits.join(' · ');
    }
    if (infoDescription) {
      infoDescription.textContent = book.description || '';
      infoDescription.style.display = book.description ? 'block' : 'none';
    }
    if (infoTags) {
      infoTags.innerHTML = '';
      if (Array.isArray(book.tags)) {
        book.tags.forEach((tag) => {
          const chip = document.createElement('span');
          chip.textContent = `#${tag}`;
          infoTags.appendChild(chip);
        });
      }
    }
    if (infoButton) {
      if (book.presentation) {
        const href = book.presentation.startsWith('http') ? book.presentation : `${book.presentation}`;
        infoButton.href = href;
        infoButton.target = '_blank';
      } else {
        infoButton.href = '#';
        infoButton.removeAttribute('target');
      }
    }
    infoPanel.classList.add('visible');
  }

  function setupMotion() {
    if (!stackWrapper || document.body.classList.contains('is-mobile')) {
      return;
    }
    if (motionInitialized) {
      return;
    }
    let rafId = null;
    let targetX = 10;
    let targetY = 0;
    let currentX = targetX;
    let currentY = targetY;
    let glowTilt = { x: 0, y: 0 };

    const animate = () => {
      currentX += (targetX - currentX) * 0.08;
      currentY += (targetY - currentY) * 0.08;
      stackWrapper.style.setProperty('--tilt-x', `${currentX}deg`);
      stackWrapper.style.setProperty('--tilt-y', `${currentY}deg`);
      const lift = Math.max(0, 6 - Math.abs(currentY)) * 1.2;
      stackWrapper.style.setProperty('--lift', `${lift}px`);

      if (parallax) {
        glowTilt.x += (targetY * 0.3 - glowTilt.x) * 0.06;
        glowTilt.y += (targetX * -0.4 - glowTilt.y) * 0.06;
        parallax.style.transform = `rotateY(${glowTilt.x}deg) rotateX(${glowTilt.y}deg)`;
      }

      rafId = requestAnimationFrame(animate);
    };

    const updateTarget = (event) => {
      const rect = stackWrapper.getBoundingClientRect();
      const x = (event.clientX - rect.left) / rect.width;
      const y = (event.clientY - rect.top) / rect.height;
      targetY = (x - 0.5) * 18;
      targetX = 9 - (y - 0.5) * 14;
    };

    const resetTarget = () => {
      targetX = 10;
      targetY = 0;
    };

    stackWrapper.addEventListener('pointermove', updateTarget);
    stackWrapper.addEventListener('pointerleave', resetTarget);
    window.addEventListener('blur', resetTarget);

    animate();
    motionInitialized = true;
  }

  function randomRange(min, max) {
    return Math.random() * (max - min) + min;
  }
})();
