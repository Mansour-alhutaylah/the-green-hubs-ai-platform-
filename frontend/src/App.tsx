import { BrowserRouter } from 'react-router';
import { AppProviders } from '@/app/providers/AppProviders';
import { AppRoutes } from '@/app/router/routes';

export function App() {
  return (
    <BrowserRouter>
      <AppProviders>
        <AppRoutes />
      </AppProviders>
    </BrowserRouter>
  );
}
