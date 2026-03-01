// ── Swiper (testimonials carousel) ──────────────────────────────────────────
import Swiper from 'swiper';
import { Autoplay, Pagination } from 'swiper/modules';
import 'swiper/css';
import 'swiper/css/pagination';

new Swiper('.swiper', {
  modules: [Autoplay, Pagination],
  loop: true,
  autoplay: { delay: 4000, disableOnInteraction: false },
  pagination: { el: '.swiper-pagination', clickable: true },
  slidesPerView: 1,
  spaceBetween: 24,
  breakpoints: {
    640: { slidesPerView: 2 },
    1024: { slidesPerView: 3 },
  },
});

// ── Reveal sales content after 18 minutes ────────────────────────────────────
const DELAY_MS = 18 * 60 * 1000; // 18 minutes

setTimeout(() => {
  const delayed = document.getElementById('delayed-content');
  if (delayed) delayed.style.display = 'block';
}, DELAY_MS);

// ── canvas-confetti (CTA click) ──────────────────────────────────────────────
import confetti from 'canvas-confetti';

function fireConfetti() {
  confetti({
    particleCount: 120,
    spread: 80,
    origin: { y: 0.6 },
    colors: ['#d4af37', '#fff', '#b8860b', '#f0e68c'],
  });
}

document.querySelectorAll('.cta, .btn-cta').forEach(btn => {
  btn.addEventListener('click', fireConfetti);
});
