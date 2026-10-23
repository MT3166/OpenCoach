document.querySelectorAll('.exercise-editor').forEach(editor => {
  const form = editor.closest('form');
  const field = form.querySelector('[name="exercises"]');
  const rows = editor.querySelector('[data-exercise-rows]');
  const fixed = editor.dataset.fixed === 'true';
  const addRow = (data = {}) => {
    const row = editor.querySelector('template').content.firstElementChild.cloneNode(true);
    row.querySelectorAll('[data-field]').forEach(input => {
      input.value = data[input.dataset.field] ?? '';
      if (fixed && input.dataset.field === 'name') input.readOnly = true;
    });
    const remove = row.querySelector('.remove-row');
    remove.hidden = fixed;
    remove.addEventListener('click', () => { if (rows.children.length > 1) row.remove(); });
    rows.append(row);
  };
  let data = [];
  try { data = JSON.parse(field.value || '[]'); } catch { /* Preserve the server's validation message. */ }
  if (!Array.isArray(data)) data = [];
  (data.length ? data : [{}]).forEach(addRow);
  editor.querySelector('[data-add-exercise]')?.addEventListener('click', () => { if (rows.children.length < 50) addRow(); });
  form.addEventListener('submit', () => {
    field.value = JSON.stringify([...rows.children].map(row => {
      const data = {};
      row.querySelectorAll('[data-field]').forEach(input => { data[input.dataset.field] = input.value || null; });
      return data;
    }));
  });
});

document.querySelectorAll('form').forEach(form => {
  form.addEventListener('submit', event => {
    if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) { event.preventDefault(); return; }
    if (form.method.toLowerCase() !== 'post') return;
    const button = event.submitter;
    if (button?.name) {
      const choice = document.createElement('input');
      choice.type = 'hidden'; choice.name = button.name; choice.value = button.value;
      form.append(choice);
    }
    form.querySelectorAll('button[type="submit"], button:not([type])').forEach(item => { item.disabled = true; });
    if (button) { button.dataset.originalText = button.textContent; button.textContent = '正在保存…'; }
  });
});

document.querySelectorAll('[data-session-form]').forEach(form => {
  const kind = form.querySelector('[name="kind"]');
  const capacity = form.querySelector('[name="capacity"]');
  const update = () => {
    capacity.readOnly = kind.value === 'private';
    capacity.min = kind.value === 'private' ? 1 : 2;
    if (kind.value === 'private') capacity.value = 1;
    else if (Number(capacity.value) < 2) capacity.value = 4;
  };
  kind.addEventListener('change', update); update();
});

document.querySelectorAll('[data-copy]').forEach(button => {
  button.addEventListener('click', async () => {
    const input = button.parentElement.querySelector('input');
    try {
      if (!navigator.clipboard) throw new Error('clipboard unavailable');
      await navigator.clipboard.writeText(input.value);
    } catch {
      input.select(); document.execCommand('copy');
    }
    button.textContent = '已复制';
    setTimeout(() => { button.textContent = '复制'; }, 1800);
  });
});
