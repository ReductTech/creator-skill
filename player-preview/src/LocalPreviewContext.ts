import {createContext, type ReactNode} from 'react';

export const LocalPreviewContext = createContext<{publish?: ReactNode} | null>(null);
