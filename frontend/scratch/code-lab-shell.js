// Project-owned emergency control outside the Scratch programming workspace.
(() => {
    const token = new URLSearchParams(window.location.search).get('code_token');
    if (!token) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = '■ EMERGENCY STOP';
    button.setAttribute('aria-label', 'Emergency stop Cozmo');
    Object.assign(button.style, {
        position: 'fixed', top: '6px', right: '8px', zIndex: '2147483647',
        background: '#bb1f32', color: 'white', border: '2px solid white',
        borderRadius: '6px', padding: '6px 10px', fontWeight: 'bold', cursor: 'pointer'
    });
    button.addEventListener('click', async () => {
        button.disabled = true;
        try {
            const response = await fetch('/api/emergency-stop', {
                method: 'POST', headers: {'X-Code-Token': token}
            });
            button.textContent = response.ok ? '■ STOP ACTIVE' : '■ STOP FAILED';
        } catch (_error) {
            button.textContent = '■ STOP FAILED';
        } finally {
            button.disabled = false;
            window.setTimeout(() => { button.textContent = '■ EMERGENCY STOP'; }, 3000);
        }
    });
    document.body.appendChild(button);
})();
