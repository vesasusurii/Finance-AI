export type PercentileSummary = {
  p50: number | null;
  p90: number | null;
  p95: number | null;
  p99: number | null;
};

export type SlowJobEntry = {
  document_id: number | null;
  extraction_mode: string | null;
  total_ms: number | null;
  openai_total_ms: number | null;
  queue_wait_ms: number | null;
  render_ms?: number | null;
  merge_ms?: number | null;
  openai_call_count: number | null;
  slowness_reason: string;
  slo_violations: string[];
  violations?: string[];
};

export type OcrAnalytics = {
  sample_size: number;
  percentiles: {
    total_ms: PercentileSummary;
    openai_total_ms: PercentileSummary;
    queue_wait_ms: PercentileSummary;
    render_ms: PercentileSummary;
  };
  averages: {
    openai_call_count: number;
    pipeline_overlap_saved_ms: number;
  };
  distributions: Record<string, Record<string, number>>;
  rates: {
    targeted_recovery_usage: number;
    fallback_usage: number;
  };
  slow_jobs: SlowJobEntry[];
  slo_violations: SlowJobEntry[];
  slo_config: {
    total_ms: number;
    openai_ms: number;
    queue_wait_ms: number;
    max_openai_calls: number;
    max_fallback_rate: number;
  };
};

export type WorkerMetricsResponse = {
  ocr_queue_size: number;
  ocr_high_priority_queue_size: number;
  ocr_normal_queue_size: number;
  review_queue_size: number;
  transaction_queue_size: number;
  ocr_avg_duration_ms: number;
  worker_avg_duration_ms: number;
  failure_rate_5m: number;
  openai_avg_latency_ms: number;
  queue_class_distribution: Record<string, number>;
  avg_queue_wait_ms_by_class: Record<string, number>;
  avg_pipeline_overlap_saved_ms: number;
  ocr_analytics: OcrAnalytics;
  system_mode: string;
  recent_ocr_timings: Record<string, unknown>[];
};
