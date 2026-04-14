import { useEffect, useState } from 'react';

export default function useScrollbarWidth() {
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const getWidth = () => {
      const outer = document.createElement('div');
      outer.style.visibility = 'hidden';
      outer.style.overflow = 'scroll';
      document.body.appendChild(outer);

      const inner = document.createElement('div');
      outer.appendChild(inner);

      const scrollbarWidth = outer.offsetWidth - inner.offsetWidth;
      document.body.removeChild(outer);

      setWidth(scrollbarWidth);
    };

    getWidth();

    window.addEventListener('resize', getWidth);
    return () => window.removeEventListener('resize', getWidth);
  }, []);

  return width;
}
