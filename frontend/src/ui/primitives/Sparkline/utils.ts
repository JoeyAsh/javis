export function buildPath(data: number[], vw: number, vh: number): string {
    if (data.length < 2) return '';
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const pad = 2;
    const points = data.map((v, i) => {
        const x = (i / (data.length - 1)) * vw;
        const y = vh - pad - ((v - min) / range) * (vh - pad * 2);
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    });
    return points.join(' ');
}
