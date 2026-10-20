const form = document.querySelector('#signup-form');
const status = document.querySelector('#form-status');
const success = document.querySelector('#signup-success');

form?.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  const button = form.querySelector('button[type="submit"]');
  if (button.disabled) return;
  const values = new FormData(form);
  button.disabled = true;
  button.querySelector('span').textContent = 'Saving your signup…';
  status.textContent = '';
  status.classList.remove('is-error');
  try {
    const response = await fetch('/api/waitlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: values.get('email'), name: values.get('name'), role: values.get('role'),
        consent: values.get('consent') === 'on', website: values.get('website'),
      }),
      signal: AbortSignal.timeout(15000),
    });
    const result = await response.json();
    if (!response.ok || result.ok !== true) throw new Error(result.error || 'We couldn’t save your signup. Please try again.');
    form.hidden = true;
    success.hidden = false;
    success.focus({ preventScroll: true });
  } catch (error) {
    status.classList.add('is-error');
    status.textContent = error.name === 'TimeoutError' || error instanceof TypeError
      ? 'We couldn’t confirm your signup. Check your connection and try again; submitting twice won’t add you twice.'
      : error.message;
  } finally {
    button.disabled = false;
    button.querySelector('span').textContent = 'Join the early-access list';
  }
});
