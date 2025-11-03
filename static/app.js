const single = document.getElementById('form-single');
const result = document.getElementById('result');
const batchBtn = document.getElementById('btn-batch');
const batchBox = document.getElementById('batch-json');
const batchResult = document.getElementById('batch-result');

if (single) {
  single.addEventListener('submit', async (e) => {
    e.preventDefault();
    result.classList.remove('hide');
    result.innerHTML = '⏳ Creating video…';

    const fd = new FormData(single);
    const res = await fetch('/create', { method: 'POST', body: fd });
    const json = await res.json();
    if (!json.ok) {
      result.innerHTML = '❌ ' + (json.error || 'Failed');
      return;
    }
    result.innerHTML = '✅ Done! <a href="/download/' + json.file + '">Download video</a>';
  });
}

if (batchBtn) {
  batchBtn.addEventListener('click', async () => {
    batchResult.classList.remove('hide');
    batchResult.innerHTML = '⏳ Creating episodes…';

    try {
      const payload = JSON.parse(batchBox.value);
      const res = await fetch('/batch', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const json = await res.json();
      if (!json.ok) {
        batchResult.innerHTML = '❌ ' + (json.error || 'Failed');
        return;
      }
      const links = json.episodes.map(ep =>
        `<li>Ep ${ep.chapter}: <a href="/download/${json.project}/${ep.file}">${ep.title}</a></li>`
      ).join('');
      batchResult.innerHTML = `<p>✅ Done! Playlist text (copy to YouTube description):</p>
      <pre>${json.playlist_text}</pre>
      <ul>${links}</ul>`;
    } catch (e) {
      batchResult.innerHTML = '❌ Invalid JSON';
    }
  });
}
