/* global THREE */

(function initBookshelf() {
  const canvas = document.getElementById('shelf-canvas');
  const infoPanel = document.getElementById('info-panel');
  const infoCover = document.getElementById('info-cover');
  const infoTitle = document.getElementById('info-title');
  const infoMeta = document.getElementById('info-meta');
  const infoDescription = document.getElementById('info-description');
  const infoTags = document.getElementById('info-tags');
  const infoButton = document.getElementById('info-button');
  const emptyState = document.getElementById('empty-state');

  if (!canvas || !window.THREE) {
    console.warn('Three.js not available.');
    if (emptyState) {
      emptyState.textContent = 'Three.js를 불러오지 못했습니다.';
    }
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
      runThreeScene(books);
    })
    .catch((err) => {
      console.error(err);
      if (emptyState) {
        emptyState.style.display = 'flex';
        emptyState.textContent = '책 데이터를 불러오는 데 실패했습니다.';
      }
    });

  function runThreeScene(books) {
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x080b16, 0.16);

    const camera = new THREE.PerspectiveCamera(36, canvas.clientWidth / canvas.clientHeight || 1, 0.1, 100);
    camera.position.set(0, 2.4, 9);

    const ambient = new THREE.AmbientLight(0xffffff, 0.75);
    const keyLight = new THREE.DirectionalLight(0xfff1cb, 1.2);
    keyLight.position.set(8, 11, 6);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(1024, 1024);
    const fillLight = new THREE.DirectionalLight(0x88aaff, 0.5);
    fillLight.position.set(-6, 6, -5);
    const rimLight = new THREE.DirectionalLight(0xff9f6a, 0.6);
    rimLight.position.set(0, 4, 10);
    scene.add(ambient, keyLight, fillLight, rimLight);

    const shelfGroup = new THREE.Group();
    scene.add(shelfGroup);

    const perShelf = Math.max(7, Math.ceil(books.length / 3));
    const shelfCount = Math.min(3, Math.ceil(books.length / perShelf));

    const shelfMaterial = new THREE.MeshStandardMaterial({
      color: 0x372214,
      roughness: 0.65,
      metalness: 0.08,
    });

    for (let i = 0; i < shelfCount; i += 1) {
      const width = perShelf * 0.68 + 1.8;
      const board = new THREE.Mesh(new THREE.BoxGeometry(width, 0.12, 2.6), shelfMaterial);
      board.position.set(0, 1.4 - i * 1.8, -0.4);
      board.receiveShadow = true;
      shelfGroup.add(board);
    }

    const textureLoader = new THREE.TextureLoader();
    textureLoader.crossOrigin = 'anonymous';

    const spineColors = [0xf1c27d, 0xf4b183, 0xe0a15a, 0xd48255, 0xbb643a];

    const bookMeshes = books.map((book, index) => {
      const width = THREE.MathUtils.randFloat(0.46, 0.62);
      const height = THREE.MathUtils.randFloat(1.35, 1.55);
      const depth = THREE.MathUtils.randFloat(0.22, 0.32);
      const geometry = new THREE.BoxGeometry(width, height, depth);

      const spineColor = new THREE.Color(spineColors[index % spineColors.length] || 0xd58c5c);
      const sideMaterial = new THREE.MeshStandardMaterial({
        color: spineColor,
        roughness: 0.52,
        metalness: 0.08,
      });
      const topMaterial = new THREE.MeshStandardMaterial({ color: 0xfdf5e3, roughness: 0.35 });
      const coverMaterial = new THREE.MeshStandardMaterial({ color: 0xf7e4d4, roughness: 0.42 });

      const materials = [sideMaterial, sideMaterial, topMaterial, topMaterial, coverMaterial, coverMaterial];
      const mesh = new THREE.Mesh(geometry, materials);
      mesh.castShadow = true;
      mesh.receiveShadow = true;

      const shelfIndex = Math.floor(index / perShelf);
      const positionInShelf = index % perShelf;
      const spread = Math.max(perShelf - 1, 1) * 0.68;
      mesh.position.x = positionInShelf * 0.68 - spread / 2;
      mesh.position.y = 1.48 - shelfIndex * 1.8;
      mesh.position.z = THREE.MathUtils.randFloat(-0.2, 0.25);
      mesh.rotation.y = THREE.MathUtils.degToRad(THREE.MathUtils.randFloat(-8, 8));

      const coverUrl = book.cover || '/assets/covers/default.svg';
      textureLoader.load(
        coverUrl,
        (tex) => {
          tex.colorSpace = THREE.SRGBColorSpace;
          tex.anisotropy = 8;
          materials[4] = new THREE.MeshStandardMaterial({ map: tex, roughness: 0.34, metalness: 0.12 });
          materials[5] = new THREE.MeshStandardMaterial({ map: tex, roughness: 0.38, metalness: 0.1 });
          mesh.material = materials;
        },
        undefined,
        () => {
          mesh.material = materials; // keep fallback colors
        }
      );

      mesh.userData = book;
      shelfGroup.add(mesh);
      return mesh;
    });

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let hovered = null;

    function resizeRenderer() {
      const width = canvas.clientWidth || window.innerWidth;
      const height = canvas.clientHeight || window.innerHeight;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    }

    function updateInfoPanel(book) {
      if (!infoPanel) return;
      if (!book) {
        if (infoDescription) {
          infoDescription.textContent = '';
        }
        infoPanel.classList.remove('visible');
        return;
      }
      const cover = book.cover || '/assets/covers/default.svg';
      if (infoCover) {
        infoCover.src = cover;
        infoCover.alt = book.title || '책 표지';
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
        infoButton.href = book.presentation || '#';
        infoButton.target = book.presentation ? '_blank' : '_self';
        infoButton.dataset.slug = book.slug || '';
      }
      infoPanel.classList.add('visible');
    }

    function onPointerMove(event) {
      const rect = canvas.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    }

    function onClick() {
      if (hovered && hovered.object && hovered.object.userData) {
        const { presentation } = hovered.object.userData;
        if (presentation) {
          window.open(presentation, '_blank');
        }
      }
    }

    function render() {
      shelfGroup.rotation.y += 0.0025;

      raycaster.setFromCamera(pointer, camera);
      const intersects = raycaster.intersectObjects(bookMeshes);
      if (intersects.length) {
        const match = intersects[0];
        if (!hovered || hovered.object !== match.object) {
          if (hovered && hovered.object) hovered.object.scale.set(1, 1, 1);
          hovered = match;
          hovered.object.scale.set(1.05, 1.06, 1.05);
          updateInfoPanel(hovered.object.userData);
          canvas.style.cursor = 'pointer';
        }
      } else if (hovered) {
        hovered.object.scale.set(1, 1, 1);
        hovered = null;
        updateInfoPanel(null);
        canvas.style.cursor = 'default';
      }
      renderer.render(scene, camera);
      requestAnimationFrame(render);
    }

    window.addEventListener('resize', resizeRenderer);
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('click', onClick);

    resizeRenderer();
    render();
  }
})();
