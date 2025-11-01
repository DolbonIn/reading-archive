(function initBookshelf() {
  const shelf = document.getElementById('bookshelf');
  const wrapper = document.querySelector('.bookshelf');
  const infoPanel = document.getElementById('info-panel');
  const infoCover = document.getElementById('info-cover');
  const infoTitle = document.getElementById('info-title');
  const infoMeta = document.getElementById('info-meta');
  const infoDescription = document.getElementById('info-description');
  const infoTags = document.getElementById('info-tags');
  const infoButton = document.getElementById('info-button');
  const emptyState = document.getElementById('empty-state');

  if (!shelf) {
    return;
  }

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
    books.forEach((book, index) => {
      const card = document.createElement('article');
      card.className = 'book-card';
      card.style.setProperty('--twist', `${randomRange(-3, 3)}deg`);
      card.setAttribute('role', 'button');
      card.setAttribute('tabindex', '0');
      card.setAttribute('aria-label', `${book.title || '책'} 보기`);

      const coverSrc = book.cover || 'assets/covers/default.svg';
      const img = document.createElement('img');
      img.src = coverSrc;
      img.alt = book.title ? `${book.title} 표지` : '책 표지';
      img.loading = 'lazy';

      const reflection = document.createElement('span');
      reflection.className = 'reflection';

      card.appendChild(img);
      card.appendChild(reflection);

      const showInfo = () => updateInfoPanel(book);
      const openPresentation = () => {
        if (book.presentation) {
          const url = book.presentation.startsWith('http') ? book.presentation : `${book.presentation}`;
          window.open(url, '_blank');
        }
      };

      card.addEventListener('mouseenter', showInfo);
      card.addEventListener('focus', showInfo);
      card.addEventListener('click', openPresentation);
      card.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          openPresentation();
        }
      });

      fragment.appendChild(card);
    });
    shelf.innerHTML = '';
    shelf.appendChild(fragment);
  }

  function updateInfoPanel(book) {
    if (!infoPanel) return;
    if (!book) {
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
    if (!wrapper) return;
    let rafId = null;
    let targetX = 8;
    let targetY = 0;
    let currentX = targetX;
    let currentY = targetY;

    const animate = () => {
      currentX += (targetX - currentX) * 0.08;
      currentY += (targetY - currentY) * 0.08;
      wrapper.style.setProperty('--tilt-x', `${currentX}deg`);
      wrapper.style.setProperty('--tilt-y', `${currentY}deg`);
      rafId = requestAnimationFrame(animate);
    };

    const updateTarget = (event) => {
      const rect = wrapper.getBoundingClientRect();
      const x = (event.clientX - rect.left) / rect.width;
      const y = (event.clientY - rect.top) / rect.height;
      targetY = (x - 0.5) * 20;
      targetX = 6 - (y - 0.5) * 10;
    };

    const resetTarget = () => {
      targetX = 8;
      targetY = 0;
    };

    window.addEventListener('mousemove', updateTarget);
    window.addEventListener('mouseleave', resetTarget);
    window.addEventListener('blur', resetTarget);

    animate();
  }

  function randomRange(min, max) {
    return Math.random() * (max - min) + min;
  }
})();
