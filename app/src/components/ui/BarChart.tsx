import {
  Chart,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions,
} from 'chart.js';
import React from 'react';
import { Bar } from 'react-chartjs-2';
import resolveConfig from 'tailwindcss/resolveConfig';

import { BarChartProps } from '@/types';

import tailwindConfig from '../../../tailwind.config';

const fullConfig = resolveConfig(tailwindConfig);

Chart.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const textColor = fullConfig.theme.colors.gray[300];

const defaultColors = [
  fullConfig.theme.colors.blue[500],
  fullConfig.theme.colors.red[500],
  fullConfig.theme.colors.yellow[500],
  fullConfig.theme.colors.teal[500],
  fullConfig.theme.colors.purple[500],
  fullConfig.theme.colors.orange[500],
];

type FilterDisplayNames = {
  [key: string]: string;
  search_latency: string;
  search_metrics: string;
  rag_generation_latency: string;
  error: string;
};

const filterDisplayNames: FilterDisplayNames = {
  search_latency: 'Search Latency',
  search_metrics: 'Search Metrics',
  rag_generation_latency: 'RAG Latency',
  error: 'Errors',
};

const createHistogramData = (data: number[], label: string) => {
  if (!Array.isArray(data)) {
    console.error('Data passed to createHistogramData is not an array:', data);
    return {
      labels: [],
      datasets: [],
    };
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const binCount = 10;
  const binSize = (max - min) / binCount;

  const bins = Array.from({ length: binCount }, (_, i) => min + i * binSize);
  const histogram = bins.map((bin, index) => {
    const nextBin = bins[index + 1] ?? max + binSize;
    if (index === bins.length - 1) {
      return data.filter((value) => value >= bin && value <= max).length;
    }
    return data.filter((value) => value >= bin && value < nextBin).length;
  });

  return {
    labels: bins.map((bin, index) => {
      const nextBin = bins[index + 1] ?? max;
      return `${bin.toFixed(1)} - ${nextBin.toFixed(1)}`;
    }),
    datasets: [
      {
        label,
        backgroundColor: defaultColors[0],
        borderColor: defaultColors[0],
        borderWidth: 1,
        data: histogram,
        barPercentage: 1,
        categoryPercentage: 1,
      },
    ],
  };
};

const BarChart: React.FC<BarChartProps> = ({ data, selectedFilter }) => {
  const filteredLogs = data.filtered_logs?.[selectedFilter] || [];

  const values = filteredLogs.map((entry) => parseFloat(entry.value));
  const chartData = createHistogramData(
    values,
    filterDisplayNames[selectedFilter] || selectedFilter
  );

  const chartOptions: ChartOptions<'bar'> = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          color: textColor,
        },
      },
      title: {
        display: true,
        text: `${filterDisplayNames[selectedFilter] || selectedFilter} Histogram`,
        color: textColor,
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            const label = context.dataset.label || '';
            const value = context.parsed.y;
            const range = context.label;
            return `${label}: ${value} (Range: ${range})`;
          },
        },
      },
    },
    scales: {
      x: {
        title: {
          display: true,
          text: filterDisplayNames[selectedFilter] || selectedFilter,
          color: textColor,
        },
        ticks: {
          color: textColor,
          maxRotation: 45,
          minRotation: 45,
        },
        grid: {
          offset: true,
        },
      },
      y: {
        title: {
          display: true,
          text: 'Count',
          color: textColor,
        },
        ticks: {
          color: textColor,
        },
        beginAtZero: true,
      },
    },
  };

  return (
    <div className="relative">
      <Bar data={chartData} options={chartOptions} />
      {filteredLogs.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-50 text-white">
          No data available
        </div>
      )}
    </div>
  );
};

export default BarChart;
