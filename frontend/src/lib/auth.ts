import { api, ApiError, profileComplete, useSession, type User } from '../api';
import { DEMO_ADMIN, type DemoCompany } from './demo';

/** Вход по email и паролю: токены → профиль из /auth/me */
export async function signIn(email: string, password: string, demo = false): Promise<User> {
  const t = await api.login(email, password);
  const s = useSession.getState();
  s.setTokens(t.access_token, t.refresh_token);
  s.setDemo(demo ? { email, password } : null);
  const me = await api.me();
  s.setUser(me);
  return me;
}

export async function signUp(username: string, email: string, password: string): Promise<User> {
  await api.register(username, email, password);
  return signIn(email, password);
}

/** Демо-компания: войти, а если аккаунта ещё нет — зарегистрировать и заполнить профиль */
export async function signInDemo(d: DemoCompany): Promise<User> {
  let me: User;
  try {
    me = await signIn(d.email, d.password, true);
  } catch (e) {
    if (!(e instanceof ApiError) || e.status !== 400) throw e;
    try {
      await api.register(d.username, d.email, d.password);
    } catch (re) {
      if (re instanceof ApiError && re.status === 400) throw new ApiError(400, 'Демо-аккаунт уже есть в бэкенде, но с другим паролем');
      throw re;
    }
    me = await signIn(d.email, d.password, true);
  }
  if (!profileComplete(me)) {
    me = await api.updateMe(d.profile);
    useSession.getState().setUser(me);
  }
  return me;
}

export async function signInAdmin(): Promise<User> {
  try {
    const me = await signIn(DEMO_ADMIN.email, DEMO_ADMIN.password, true);
    if (me.role !== 'admin') throw new ApiError(403, 'Этот аккаунт не администратор');
    return me;
  } catch (e) {
    if (e instanceof ApiError && e.status === 400) {
      throw new ApiError(400, 'Не подошли данные администратора. Проверьте ADMIN_EMAIL и ADMIN_PASSWORD в .env бэкенда');
    }
    throw e;
  }
}

export async function signOut() {
  try {
    await api.logout();
  } catch {
    /* токен мог уже истечь — всё равно выходим */
  }
  useSession.getState().clear();
}
