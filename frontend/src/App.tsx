import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { BasicLayout } from './layouts/BasicLayout'
import { HomePage } from './pages/HomePage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<BasicLayout />}>
          <Route index element={<HomePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
