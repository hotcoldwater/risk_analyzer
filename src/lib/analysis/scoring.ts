export const benchmarkConfig = {
  defaultMode: "weighted_average",
  weights: {
    companyTrend: 0.3,
    industryMedian: 0.35,
    sizeSimilarPeer: 0.25,
    manualPeer: 0.1
  },
  sensitivity: {
    conservative: 95,
    standard: 90,
    sensitive: 75
  }
} as const;
