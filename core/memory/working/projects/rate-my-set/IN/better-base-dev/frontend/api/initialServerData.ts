import { type InitialData } from './types/initialData';

const _cached: { value: InitialData | null } = { value: null };

export const getInitialServerData = (): InitialData => {
  if (_cached.value == null) {
    const el = document.getElementById('initial_server_data_provided_for_web') as HTMLElement;
    const initialData = JSON.parse(el.textContent || '') as InitialData;
    _cached.value = initialData;
  }

  return _cached.value;
};
