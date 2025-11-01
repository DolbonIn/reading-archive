(function () {
  const form = document.getElementById('upload-form');
  const fileInput = document.getElementById('pdf-input');
  const dropzone = document.getElementById('dropzone');
  const statusBox = document.getElementById('status-box');
  const statusMessage = document.getElementById('status-message');
  const statusProgress = document.getElementById('status-progress');
  const statusLink = document.getElementById('status-link');
  const submitButton = document.getElementById('submit-button');

  if (!form) return;

  const renderProgress = (progress = []) => {
    if (!statusProgress) return;
    statusProgress.innerHTML = '';
    if (!progress || !progress.length) return;
    progress.forEach((item) => {
      const line = document.createElement('div');
      line.textContent = item;
      statusProgress.appendChild(line);
    });
  };

  const setStatus = (message, type, progress = []) => {
    statusBox.classList.remove('success', 'error', 'pending');
    if (type) statusBox.classList.add(type);
    statusBox.classList.add('active');
    statusMessage.textContent = message;
    renderProgress(progress);
    statusLink.innerHTML = '';
  };

  const clearStatus = () => {
    statusBox.classList.remove('active', 'success', 'error', 'pending');
    statusMessage.textContent = '';
    statusLink.innerHTML = '';
    renderProgress([]);
  };

  const filesFromEvent = (event) => {
    if (event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files.length) {
      return event.dataTransfer.files;
    }
    return null;
  };

  const onFileSelected = (file) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setStatus('PDF 파일만 업로드할 수 있습니다.', 'error');
      fileInput.value = '';
      return;
    }
    clearStatus();
    fileInput.files = (function () {
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(file);
      return dataTransfer.files;
    })();
    dropzone.classList.remove('active');
    dropzone.querySelector('.dropzone-filename').textContent = file.name;
  };

  dropzone.addEventListener('click', () => {
    fileInput.click();
  });

  fileInput.addEventListener('change', (event) => {
    onFileSelected(event.target.files[0]);
  });

  ['dragenter', 'dragover'].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      dropzone.classList.add('active');
    });
  });

  ['dragleave', 'dragend'].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      dropzone.classList.remove('active');
    });
  });

  dropzone.addEventListener('drop', (event) => {
    event.preventDefault();
    event.stopPropagation();
    dropzone.classList.remove('active');
    const files = filesFromEvent(event);
    if (files && files[0]) {
      onFileSelected(files[0]);
    }
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearStatus();

    const file = fileInput.files[0];
    if (!file) {
      setStatus('먼저 PDF 파일을 선택해주세요.', 'error');
      return;
    }

    submitButton.disabled = true;
    submitButton.textContent = '생성 중...';
    setStatus('Gemini 프레젠테이션을 생성하는 중입니다.', 'pending');

    const formData = new FormData(form);
    formData.set('dry_run', form.querySelector('#dry-run').checked ? 'true' : 'false');
    formData.set('commit', form.querySelector('#commit').checked ? 'true' : 'false');
    formData.set('push', form.querySelector('#push').checked ? 'true' : 'false');

    try {
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || '업로드 실패');
      }
      const data = payload.data;
      const progressLog = Array.isArray(data.progress) ? data.progress : [];
      setStatus('AI 프레젠테이션 생성이 완료되었습니다.', 'success', progressLog);
      if (data && data.presentation) {
        statusLink.innerHTML = `<a href="${data.presentation}" target="_blank" rel="noopener">프레젠테이션 열기 →</a>`;
      }
    } catch (error) {
      setStatus(error.message || '처리 중 오류가 발생했습니다.', 'error');
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = 'AI 프레젠테이션 생성';
    }
  });
})();
