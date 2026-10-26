import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const css = readFileSync(new URL('./developer-platform.css', import.meta.url), 'utf8');

describe('developer platform popup notifications', () => {
  it('uses distinct red error and emerald success borders and typography', () => {
    expect(css).toContain('.dp-toast-popup.error{border-color:#ff646b');
    expect(css).toContain('.dp-toast-popup.success{border-color:#36d98d');
    expect(css).toContain('.dp-toast-popup.error .dp-toast-copy strong{color:#ff969c}');
    expect(css).toContain('.dp-toast-popup.success .dp-toast-copy strong{color:#7ff0b0}');
  });

  it('provides a visible close control, timestamp styles, responsive layout and reduced motion', () => {
    expect(css).toContain('.dp-toast-close');
    expect(css).toContain('.dp-toast-copy time');
    expect(css).toContain('@media(max-width:600px)');
    expect(css).toContain('prefers-reduced-motion:reduce');
  });
});
