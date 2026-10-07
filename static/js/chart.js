/**
 * High-performance Vanilla Canvas Chart for Real-Time Streaming Telemetry
 */
class RealTimeStreamChart {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.maxPoints = 35;
        this.dataPoints = []; // { time: string, approved: number, blocked: number }

        // Initialize with baseline data
        for (let i = 0; i < this.maxPoints; i++) {
            this.dataPoints.push({
                approved: Math.floor(Math.random() * 4) + 1,
                blocked: Math.random() < 0.15 ? 1 : 0
            });
        }

        this.render();
    }

    pushData(isBlocked) {
        if (!this.canvas) return;
        const currentBucket = this.dataPoints[this.dataPoints.length - 1];
        if (isBlocked) {
            currentBucket.blocked += 1;
        } else {
            currentBucket.approved += 1;
        }
    }

    tick() {
        if (!this.canvas) return;
        // Shift data points every second
        this.dataPoints.shift();
        this.dataPoints.push({ approved: 0, blocked: 0 });
        this.render();
    }

    render() {
        if (!this.canvas) return;
        const ctx = this.ctx;
        const width = this.canvas.width;
        const height = this.canvas.height;

        ctx.clearRect(0, 0, width, height);

        // Grid lines
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.lineWidth = 1;
        for (let y = 30; y < height; y += 40) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(width, y);
            ctx.stroke();
        }

        const step = width / (this.maxPoints - 1);
        const maxVal = Math.max(8, ...this.dataPoints.map(d => d.approved + d.blocked));

        // Draw Approved Stream Area
        ctx.beginPath();
        ctx.moveTo(0, height);
        this.dataPoints.forEach((pt, i) => {
            const x = i * step;
            const y = height - (pt.approved / maxVal) * (height - 25);
            if (i === 0) ctx.lineTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.lineTo(width, height);
        ctx.closePath();

        const gradApproved = ctx.createLinearGradient(0, 0, 0, height);
        gradApproved.addColorStop(0, 'rgba(6, 182, 212, 0.3)');
        gradApproved.addColorStop(1, 'rgba(6, 182, 212, 0.01)');
        ctx.fillStyle = gradApproved;
        ctx.fill();

        // Stroke Approved Line
        ctx.beginPath();
        this.dataPoints.forEach((pt, i) => {
            const x = i * step;
            const y = height - (pt.approved / maxVal) * (height - 25);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = '#06b6d4';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Draw Blocked Fraud Spikes
        this.dataPoints.forEach((pt, i) => {
            if (pt.blocked > 0) {
                const x = i * step;
                const y = height - ((pt.approved + pt.blocked) / maxVal) * (height - 25);

                // Crimson pulse circle
                ctx.beginPath();
                ctx.arc(x, Math.max(12, y), 5, 0, 2 * Math.PI);
                ctx.fillStyle = '#ef4444';
                ctx.fill();
                ctx.strokeStyle = '#fca5a5';
                ctx.lineWidth = 1.5;
                ctx.stroke();
            }
        });
    }
}
