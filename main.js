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

// ── canvas-confetti (CTA click) ──────────────────────────────────────────────
import confetti from 'canvas-confetti';

// reveal the call‑to‑action and offer copy after 18 minutes (1 080 000 ms)
setTimeout(() => {
  const cta = document.querySelector('.cta');
  const offer = document.getElementById('offer-details');
  if (cta) cta.style.display = 'inline-flex';
  if (offer) offer.style.display = 'block';
}, 1080000);

document.querySelector('.cta').addEventListener('click', (e) => {
  e.preventDefault();
  confetti({
    particleCount: 120,
    spread: 80,
    origin: { y: 0.6 },
    colors: ['#d4af37', '#fff', '#b8860b', '#f0e68c'],
  });
});
