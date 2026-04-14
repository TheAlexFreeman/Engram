export function calculateReductionsForNumber(n: number): number[] {
  let val = n;
  const reductions: number[] = [n];
  while (val >= 10) {
    if (val % 10 == 0) {
      val = Math.floor(val / 10);
    } else {
      const digits = val.toString().split('').map(Number);
      val = digits.reduce((acc, cur) => acc + cur, 0);
    }
    reductions.push(val);
  }
  return reductions;
}
