export interface Source {
  id: number; name: string; url: string; type: 'm3u' | 'txt';
  enabled: number; use_proxy: number; sort: number; note: string;
  fail_count: number; last_ok_at: string | null;
}
export interface Alias {
  id: number; canonical: string; pattern: string; is_regex: number; enabled: number;
}
export interface Template {
  id: number; canonical: string; group_title: string; logo: string;
  sort: number; enabled: number;
}
export interface Channel {
  id: number; name: string; group_title: string; url: string; logo: string;
  tvg_id: string; tvg_name: string; source: string; status: string;
  detail: string; resolution: number; speed: number; delay: number;
}
export interface TaskStatus {
  status: string; stage: string; run_id: number | null;
  started_at: string | null; logs: string[];
}
export interface Schedule {
  update_mode: 'interval' | 'time'; update_interval: number;
  update_times: string[]; update_startup: boolean; time_zone: string;
}
export interface Report {
  groups: Record<string, number>; resolution: Record<string, number>;
  sources: Source[]; runs: Array<{ id: number; started_at: string;
    finished_at: string | null; status: string; stats_json: string }>;
}
