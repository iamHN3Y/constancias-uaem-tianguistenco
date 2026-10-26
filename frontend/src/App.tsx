import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AnimatePresence } from "framer-motion";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { RequireAdmin, RequireAuth } from "./components/RequireAuth";
import { DialogProvider } from "./context/DialogContext";
import { ThemeProvider } from "./context/ThemeContext";
import { ToastProvider } from "./context/ToastContext";
import { TourProvider } from "./context/TourContext";
import { Carreras } from "./pages/Carreras";
import { Datos } from "./pages/Datos";
import { Generar } from "./pages/Generar";
import { Home } from "./pages/Home";
import { Login } from "./pages/Login";
import { Plantillas } from "./pages/Plantillas";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false },
  },
});

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <AnimatePresence mode="sync" initial={false}>
      <Routes location={location} key={location.pathname}>
        <Route path="/login" element={<Login />} />
        <Route element={<RequireAuth />}>
          <Route path="/" element={<Home />} />
          <Route path="/generar" element={<Generar />} />
          <Route element={<RequireAdmin />}>
            <Route path="/datos" element={<Datos />} />
            <Route path="/plantillas" element={<Plantillas />} />
            <Route path="/carreras" element={<Carreras />} />
          </Route>
        </Route>
      </Routes>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ToastProvider>
          <DialogProvider>
            <BrowserRouter>
              <TourProvider>
                <AnimatedRoutes />
              </TourProvider>
            </BrowserRouter>
          </DialogProvider>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
