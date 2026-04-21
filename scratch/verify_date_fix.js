
const normalizeDate = (dateStr) => {
    if (!dateStr) return dateStr;
    const parts = dateStr.split(/[\/\-\.\s]+/).filter(Boolean);
    if (parts.length === 3) {
      let d, m, y;
      if (parts[0].length === 4) { [y, m, d] = parts; }
      else if (parts[2].length === 4) { [d, m, y] = parts; }
      else { return dateStr; }
      return `${y}-${m.padStart(2, '0')}-${d.padStart(2, '0')}`;
    }
    return dateStr;
};

const testCases = [
    { input: '2003/06/30', expected: '2003-06-30' },
    { input: '30/06/2003', expected: '2003-06-30' },
    { input: '2003.06.30', expected: '2003-06-30' },
    { input: '30-06-2003', expected: '2003-06-30' },
    { input: '2003 06 30', expected: '2003-06-30' },
    { input: '06/30', expected: '06/30' }, // invalid length
    { input: '05/06/07', expected: '05/06/07' }, // ambiguous year
];

testCases.forEach(tc => {
    const output = normalizeDate(tc.input);
    console.log(`Input: ${tc.input.padEnd(12)} | Output: ${output.padEnd(12)} | ${output === tc.expected ? 'PASS' : 'FAIL'}`);
});
