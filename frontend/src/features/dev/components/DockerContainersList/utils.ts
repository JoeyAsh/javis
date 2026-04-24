export function containerPillClass(status: 'running' | 'exited' | 'restarting'): string {
    if (status === 'running') return 'pill ok';
    if (status === 'restarting') return 'pill warn';
    return 'pill err';
}
