document.addEventListener('DOMContentLoaded', () => {
  const flashMessages = document.querySelectorAll('.flash-messages li.flash');
  flashMessages.forEach(msg => {
    setTimeout(() => {
      msg.classList.add('fade-out');
    }, 5000); // Fade out after 5 seconds
  });
});
