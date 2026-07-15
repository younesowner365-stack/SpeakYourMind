window.addEventListener("DOMContentLoaded", () => {
  if (typeof Chart === "undefined") return;

  const sectionStats = window.SECTION_STATS || [];
  const satisfaction = Number(window.GLOBAL_SATISFACTION || 0);
  const sectionCanvas = document.getElementById("section-chart");
  const globalCanvas = document.getElementById("global-chart");

  if (sectionCanvas) {
    new Chart(sectionCanvas, {
      type: "bar",
      data: {
        labels: sectionStats.map(item => item.section),
        datasets: [{
          label: "Satisfaction (%)",
          data: sectionStats.map(item => item.satisfaction),
          backgroundColor: "rgba(225, 79, 30, .78)",
          borderColor: "#d94d1b",
          borderWidth: 1,
          borderRadius: 8
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: sectionStats.length > 5 ? "y" : "x",
        scales: {
          x: { beginAtZero: true, max: sectionStats.length > 5 ? 100 : undefined },
          y: { beginAtZero: true, max: sectionStats.length > 5 ? undefined : 100 }
        },
        plugins: { legend: { display: false } }
      }
    });
  }

  if (globalCanvas) {
    new Chart(globalCanvas, {
      type: "doughnut",
      data: {
        labels: ["Satisfaction", "Marge d'amélioration"],
        datasets: [{
          data: [satisfaction, Math.max(0, 100 - satisfaction)],
          backgroundColor: ["#254f9c", "#e9edf4"],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "72%",
        plugins: {
          legend: { position: "bottom" },
          tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.raw}%` } }
        }
      },
      plugins: [{
        id: "centerText",
        afterDraw(chart) {
          const { ctx, chartArea } = chart;
          if (!chartArea) return;
          ctx.save();
          ctx.font = "700 28px Segoe UI";
          ctx.fillStyle = "#18212f";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(`${satisfaction}%`, (chartArea.left + chartArea.right) / 2, (chartArea.top + chartArea.bottom) / 2);
          ctx.restore();
        }
      }]
    });
  }
});
