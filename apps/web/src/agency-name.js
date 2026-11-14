// Display alias only; the API's original agency names and identifiers stay intact.
export function agencyName(name) {
  return name === '전남광주통합특별시 무안청사' ? '전남광주특별시' : name;
}
