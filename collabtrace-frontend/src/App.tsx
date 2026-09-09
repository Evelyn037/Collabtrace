import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { RepositoryProvider } from './contexts/RepositoryContext'
import { AdminPage } from './pages/AdminPage'
import { AuthPage } from './pages/AuthPage'
import { ContributorPage } from './pages/ContributorPage'
import { DashboardPage } from './pages/DashboardPage'
import { SystemUsersPage } from './pages/SystemUsersPage'
import { ForbiddenPage, NotFoundPage } from './pages/StatusPages'
import { ProtectedRoute, RepositoryAdminRoute, SystemAdminRoute } from './routes/Guards'

export default function App() {
  return <Routes>
    <Route path="/auth" element={<AuthPage/>}/>
    <Route element={<ProtectedRoute><RepositoryProvider><AppLayout/></RepositoryProvider></ProtectedRoute>}>
      <Route path="/dashboard" element={<DashboardPage/>}/>
      <Route path="/repositories/:repositoryId/contributors/:githubUsername" element={<ContributorPage/>}/>
      <Route path="/admin" element={<RepositoryAdminRoute><AdminPage/></RepositoryAdminRoute>}/>
      <Route path="/system/users" element={<SystemAdminRoute><SystemUsersPage/></SystemAdminRoute>}/>
      <Route path="/403" element={<ForbiddenPage/>}/>
    </Route>
    <Route path="/" element={<Navigate to="/dashboard" replace/>}/>
    <Route path="*" element={<NotFoundPage/>}/>
  </Routes>
}
