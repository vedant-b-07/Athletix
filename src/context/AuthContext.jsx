import { createContext, useContext, useReducer, useEffect } from 'react';
import {
    signInWithPopup,
    signOut,
    onAuthStateChanged,
    signInWithEmailAndPassword,
    createUserWithEmailAndPassword,
    updateProfile as updateFirebaseProfile
} from 'firebase/auth';
import { auth, googleProvider, isFirebaseConfigured } from '../firebase/config';
import { UserService, AddressService, OrderService } from '../services/database';

const AuthContext = createContext();

const authReducer = (state, action) => {
    switch (action.type) {
        case 'LOGIN': {
            return {
                ...state,
                isAuthenticated: true,
                user: action.payload,
                loading: false
            };
        }

        case 'LOGOUT': {
            return {
                ...state,
                isAuthenticated: false,
                user: null,
                loading: false
            };
        }

        case 'UPDATE_PROFILE': {
            return {
                ...state,
                user: { ...state.user, ...action.payload }
            };
        }

        case 'SET_ADDRESSES': {
            return {
                ...state,
                user: { ...state.user, addresses: action.payload }
            };
        }

        case 'ADD_ADDRESS': {
            const addresses = [...(state.user?.addresses || []), action.payload];
            return {
                ...state,
                user: { ...state.user, addresses }
            };
        }

        case 'REMOVE_ADDRESS_ID': {
            const addresses = state.user?.addresses?.filter((a) => a._id !== action.payload) || [];
            return {
                ...state,
                user: { ...state.user, addresses }
            };
        }

        case 'SET_DEFAULT_ADDRESS_ID': {
            const addresses = state.user?.addresses?.map((addr) => ({
                ...addr,
                isDefault: addr._id === action.payload
            })) || [];
            return {
                ...state,
                user: { ...state.user, addresses }
            };
        }

        case 'SET_ORDERS': {
            return {
                ...state,
                user: { ...state.user, orders: action.payload }
            };
        }

        case 'ADD_ORDER': {
            const orders = [action.payload, ...(state.user?.orders || [])];
            return {
                ...state,
                user: { ...state.user, orders }
            };
        }

        case 'SET_LOADING': {
            return { ...state, loading: action.payload };
        }

        case 'LOAD_USER': {
            return action.payload;
        }

        default:
            return state;
    }
};

const initialState = {
    isAuthenticated: false,
    user: null,
    loading: true
};

const getAuthErrorMessage = (error) => {
    switch (error?.code) {
        case 'auth/operation-not-allowed':
            return 'Email/password sign-in is disabled in Firebase. Enable the Email/Password provider in Firebase Authentication.';
        case 'auth/email-already-in-use':
            return 'That email is already registered. Try signing in instead.';
        case 'auth/invalid-credential':
        case 'auth/invalid-login-credentials':
        case 'auth/user-not-found':
        case 'auth/wrong-password':
            return 'Invalid email or password.';
        case 'auth/weak-password':
            return 'Password should be at least 6 characters long.';
        default:
            return error?.message || 'Authentication failed.';
    }
};

const firebaseDisabledMessage = 'Authentication is not configured for this deployment yet. Add the Firebase Vercel environment variables to enable sign-in.';

export const AuthProvider = ({ children }) => {
    const [state, dispatch] = useReducer(authReducer, initialState);

    const hasFirebaseSession = () => auth?.currentUser?.uid && state.user?.id === auth.currentUser.uid;

    const loadBackendUser = async (firebaseUser, extraProfile = {}) => {
        const dbUser = await UserService.upsertUser({
            uid: firebaseUser.uid,
            email: firebaseUser.email,
            name: extraProfile.name || firebaseUser.displayName,
            photoURL: firebaseUser.photoURL,
            phone: extraProfile.phone ?? firebaseUser.phoneNumber ?? '',
            authProvider: extraProfile.authProvider || 'email'
        });

        const dbAddresses = await AddressService.getUserAddresses(dbUser.id) || [];
        const dbOrders = await OrderService.getUserOrders(dbUser.id) || [];

        const user = {
            id: dbUser.id,
            name: dbUser.displayName || firebaseUser.displayName || extraProfile.name || 'User',
            email: dbUser.email || firebaseUser.email || '',
            phone: dbUser.phone || extraProfile.phone || firebaseUser.phoneNumber || '',
            photoURL: dbUser.photoUrl || firebaseUser.photoURL || '',
            addresses: dbAddresses,
            orders: dbOrders,
            authProvider: dbUser.authProvider || extraProfile.authProvider || 'email',
            createdAt: dbUser.createdAt
        };

        dispatch({ type: 'LOGIN', payload: user });
        return user;
    };

    // Load user from localStorage on mount & Sync with backend
    useEffect(() => {
        const savedUser = localStorage.getItem('athletix_user');

        const syncWithDb = async (parsedUser, firebaseUid) => {
            if (parsedUser?.user?.id && firebaseUid && parsedUser.user.id === firebaseUid) {
                try {
                    const dbUser = await UserService.getUserByFirebaseUid(firebaseUid);
                    if (dbUser) {
                        const addresses = await AddressService.getUserAddresses(dbUser.id) || [];
                        const orders = await OrderService.getUserOrders(dbUser.id) || [];
                        dispatch({ 
                            type: 'LOGIN', 
                            payload: { ...parsedUser.user, addresses, orders } 
                        });
                    }
                } catch (err) {
                    console.error('Initial DB sync failed', err);
                }
            }
        };

        if (savedUser) {
            const parsed = JSON.parse(savedUser);
            dispatch({ type: 'LOAD_USER', payload: parsed });
        } else {
            dispatch({ type: 'SET_LOADING', payload: false });
        }

        if (!auth) {
            return () => {};
        }

        const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
            const parsedUser = savedUser ? JSON.parse(savedUser) : null;

            if (parsedUser?.user?.id && firebaseUser?.uid && parsedUser.user.id === firebaseUser.uid) {
                syncWithDb(parsedUser, firebaseUser.uid);
                return;
            }

            dispatch({ type: 'SET_LOADING', payload: false });
        });

        return unsubscribe;
    }, []);

    // Save user to localStorage across sessions
    useEffect(() => {
        if (!state.loading) {
            localStorage.setItem('athletix_user', JSON.stringify(state));
        }
    }, [state]);

    const register = async (userData) => {
        try {
            if (!isFirebaseConfigured() || !auth) {
                return { success: false, error: firebaseDisabledMessage };
            }
            const credential = await createUserWithEmailAndPassword(auth, userData.email, userData.password);
            await updateFirebaseProfile(credential.user, { displayName: userData.name });
            const user = await loadBackendUser(credential.user, {
                name: userData.name,
                phone: userData.phone,
                authProvider: 'email'
            });
            return { success: true, user };
        } catch (error) {
            console.error('Register error:', error);
            return { success: false, error: getAuthErrorMessage(error) };
        }
    };

    const login = async (email, password) => {
        // Demo login for testing
        if (email === 'demo@athletix.com' && password === 'demo123') {
            const demoUser = {
                id: 'dummyFirebaseUid123',
                name: 'John Doe',
                email: 'testuser@athletix.com',
                phone: '+1 234 567 8900',
                addresses: [
                    {
                        _id: 'sample_addr',
                        name: 'Demo User',
                        phone: '+91 9876543210',
                        street: '123 Sports Complex',
                        city: 'Mumbai',
                        state: 'Maharashtra',
                        pincode: '400001',
                        isDefault: true
                    }
                ],
                orders: [],
                createdAt: new Date().toISOString()
            };
            dispatch({ type: 'LOGIN', payload: demoUser });
            return { success: true, user: demoUser };
        }

        try {
            if (!isFirebaseConfigured() || !auth) {
                return { success: false, error: firebaseDisabledMessage };
            }
            const credential = await signInWithEmailAndPassword(auth, email, password);
            const user = await loadBackendUser(credential.user, { authProvider: 'email' });
            return { success: true, user };
        } catch (error) {
            console.error('Login error:', error);
            return { success: false, error: getAuthErrorMessage(error) };
        }
    };

    // Google Sign-In with MongoDB backend integration
    const loginWithGoogle = async () => {
        try {
            if (!isFirebaseConfigured() || !auth || !googleProvider) {
                return { success: false, error: firebaseDisabledMessage };
            }
            const result = await signInWithPopup(auth, googleProvider);
            const firebaseUser = result.user;
            const user = await loadBackendUser(firebaseUser, { authProvider: 'google' });
            return { success: true, user };
        } catch (error) {
            if (error?.code === 'auth/popup-closed-by-user') {
                return { success: false, error: 'Google sign-in was cancelled.' };
            }
            console.error('Google & DB login error:', error);
            return { success: false, error: error.message };
        }
    };

    const logout = async () => {
        try {
            if (state.user?.authProvider === 'google' && auth) {
                await signOut(auth);
            }
        } catch (error) {
            console.error('Logout error:', error);
        }
        dispatch({ type: 'LOGOUT' });
        localStorage.removeItem('athletix_user');
    };

    const updateProfile = async (data) => {
        try {
            if (hasFirebaseSession()) {
                await UserService.updateUser(state.user.id, data);
            }
            dispatch({ type: 'UPDATE_PROFILE', payload: data });
        } catch(e) {
            console.error(e);
        }
    };

    const addAddress = async (address) => {
        try {
            if (hasFirebaseSession()) {
                const addedAddr = await AddressService.addAddress(state.user.id, address);
                dispatch({ type: 'ADD_ADDRESS', payload: addedAddr });
                return addedAddr;
            } else {
                const localAddress = { ...address, _id: Date.now().toString() };
                dispatch({ type: 'ADD_ADDRESS', payload: localAddress });
                return localAddress;
            }
        } catch(e) {
            console.error('Error adding address', e);
            throw e;
        }
    };

    const removeAddress = async (addressId) => {
        try {
            if (hasFirebaseSession()) {
                await AddressService.deleteAddress(state.user.id, addressId);
            }
            dispatch({ type: 'REMOVE_ADDRESS_ID', payload: addressId });
        } catch(e) { console.error('Error deleting address', e); }
    };

    const setDefaultAddress = async (addressId) => {
        try {
            if (hasFirebaseSession()) {
                await AddressService.setDefaultAddress(state.user.id, addressId);
            }
            dispatch({ type: 'SET_DEFAULT_ADDRESS_ID', payload: addressId });
        } catch(e) { console.error('Error setting default addr', e); }
    };

    const addOrder = async (orderData) => {
        try {
            if (hasFirebaseSession()) {
                const newOrder = await OrderService.createOrder(state.user.id, orderData);
                dispatch({ type: 'ADD_ORDER', payload: newOrder });
                return newOrder;
            }
            const localOrder = {
                ...orderData,
                _id: `local_order_${Date.now()}`,
                orderNumber: `ATHLOCAL${Date.now()}`,
                createdAt: new Date().toISOString()
            };
            dispatch({ type: 'ADD_ORDER', payload: localOrder });
            return localOrder;
        } catch(e) {
            console.error('Error placing order', e);
            throw e;
        }
    };

    const getDefaultAddress = () => {
        return state.user?.addresses?.find(addr => addr.isDefault) || state.user?.addresses?.[0];
    };

    const value = {
        ...state,
        register,
        login,
        loginWithGoogle,
        logout,
        updateProfile,
        addAddress,
        removeAddress,
        setDefaultAddress,
        addOrder,
        getDefaultAddress
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
