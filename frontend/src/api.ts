import axios from 'axios';
import type { Source, Alias, Template, Channel, TaskStatus, Schedule, Report } from './types';

const http = axios.create({ baseURL: '/api' });

export const listSources = () => http.get<Source[]>('/sources').then(r => r.data);
export const sourceGithubUpdated = (id: number) =>
  http.get<{ id: number; updated: string | null }>(`/sources/${id}/github-updated`).then(r => r.data);
export const createSource = (d: Partial<Source>) => http.post('/sources', d).then(r => r.data);
export const updateSource = (id: number, d: Partial<Source>) => http.put(`/sources/${id}`, d).then(r => r.data);
export const deleteSource = (id: number) => http.delete(`/sources/${id}`).then(r => r.data);

export const listAliases = () => http.get<Alias[]>('/aliases').then(r => r.data);
export const createAlias = (d: Partial<Alias>) => http.post('/aliases', d).then(r => r.data);
export const updateAlias = (id: number, d: Partial<Alias>) => http.put(`/aliases/${id}`, d).then(r => r.data);
export const deleteAlias = (id: number) => http.delete(`/aliases/${id}`).then(r => r.data);

export const listTemplates = () => http.get<Template[]>('/templates').then(r => r.data);
export const createTemplate = (d: Partial<Template>) => http.post('/templates', d).then(r => r.data);
export const updateTemplate = (id: number, d: Partial<Template>) => http.put(`/templates/${id}`, d).then(r => r.data);
export const deleteTemplate = (id: number) => http.delete(`/templates/${id}`).then(r => r.data);

export const listChannels = (run = 'latest') => http.get<Channel[]>('/channels', { params: { run } }).then(r => r.data);
export const getReport = () => http.get<Report>('/reports').then(r => r.data);

export const runTask = () => http.post('/tasks/run').then(r => r.data);
export const stopTask = () => http.post('/tasks/stop').then(r => r.data);
export const getStatus = () => http.get<TaskStatus>('/tasks/status').then(r => r.data);
export const getSchedule = () => http.get<Schedule>('/tasks/schedule').then(r => r.data);
export const setSchedule = (d: Partial<Schedule>) => http.put('/tasks/schedule', d).then(r => r.data);
export const logsUrl = () => '/api/tasks/logs';  // for EventSource
export const playlistUrls = () => ({ full: '/full.m3u', compact: '/compact.m3u', txt: '/iptv.txt' });
export const proxyUrl = (u: string) => '/api/proxy?url=' + encodeURIComponent(u);
// ffmpeg-remuxed continuous MPEG-TS — compatibility path for streams that stall in browser HLS
export const restreamUrl = (u: string) => '/api/restream?url=' + encodeURIComponent(u);

export const getProxy = () => http.get<{ http_proxy: string }>('/settings/proxy').then(r => r.data);
export const setProxy = (http_proxy: string) => http.put('/settings/proxy', { http_proxy }).then(r => r.data);
