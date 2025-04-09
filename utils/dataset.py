import glob
from PIL import Image
from torch.utils import data
import os
import torch
import numpy as np
from torchvision import transforms
import random
import cv2


class dataset_DODE(data.Dataset):
    def __init__(self, train=True, arg=True):
        if train:
            self.file = '/home/lisiqi/data/DeOccDepthEstimation(DODE)/train.txt'
        else:
            self.file = '/home/lisiqi/data/DeOccDepthEstimation(DODE)/test.txt'

        self.folder = []
        self.dim = (260, 260)
        self.nb_of_bin = 36

        with open(self.file, 'r') as f:
            for line in f.readlines():
                p1 = line.strip('\n')
                self.folder.append(p1)

        self.train = train
        self.arg = arg

    def __getitem__(self, idx):
        event_vox = np.load(os.path.join(self.folder[idx], 'data', 'event.npy'))
        imgs = np.load(os.path.join(self.folder[idx], 'data', 'frame.npy'))
        mask = np.load(os.path.join(self.folder[idx], 'data', 'mask.npy'))

        gt = transforms.ToTensor()(Image.open(os.path.join(self.folder[idx], 'gt_kinect_cvt.png')))
        gt_x2 = transforms.ToTensor()(Image.open(os.path.join(self.folder[idx], 'gt_kinect_x2_cvt.png')))
        gt_x4= transforms.ToTensor()(Image.open(os.path.join(self.folder[idx], 'gt_kinect_x4_cvt.png')))

        data = np.load(os.path.join(self.folder[idx], 'data', 'flow.npy'))
        data = torch.from_numpy(data)
        event01 = data[9:9+5, ...]
        event21 = data[9+5:, ...]

        event_vox, imgs, mask, gt, gt_x2, gt_x4, event01, event21 = self.data_augmentation(event_vox, imgs, mask, gt, gt_x2, gt_x4, event01, event21, train=(self.train & self.arg))

        event_vox = event_vox.reshape([3, -1, 256, 256])
        imgs = imgs.reshape([3, -1, 256, 256])
        # gt = gt.reshape([3, 256, 256])
        mask = mask.reshape([3, -1, 256, 256]).astype(np.float32)

        return event_vox, imgs, mask, gt, gt_x2, gt_x4, event01, event21

        # event_vox = np.load(os.path.join(self.folder[idx], 'events.npy'))
        # event = np.load(os.path.join(self.folder[idx], 'events.npy'))
        # gt = transforms.ToTensor()(Image.open(os.path.join(self.folder[idx], 'gt_kinect_cvt.png')))
        # mid = int(glob.glob(os.path.join(self.folder[idx], 'frame_*_1.jpg'))[0].split('_')[-2])
        # ts = np.load(os.path.join(self.folder[idx], 'ts.npy'))
        # frames = glob.glob(os.path.join(self.folder[idx], 'frame_*.jpg'))
        # frames.sort()
        #
        # id_start = mid-8
        # id_end = mid+9
        #
        # imgs = [transforms.ToTensor()(Image.open(i)) for i in frames]
        #
        # imgs_0 = torch.cat(imgs[id_start-1:id_end-1], dim=0)
        # imgs_1 = torch.cat(imgs[id_start:id_end], dim=0)
        # imgs_2 = torch.cat(imgs[id_start+1:id_end+1], dim=0)
        # imgs = torch.stack([imgs_0, imgs_1, imgs_2], dim=0)
        #
        # event0 = event[(event[:, 0] >= ts[id_start-1][0]) & (event[:, 0] <= ts[id_end-2][1]), :].astype(np.long)
        # event1 = event[(event[:, 0] >= ts[id_start][0]) & (event[:, 0] <= ts[id_end-1][1]), :].astype(np.long)
        # event2 = event[(event[:, 0] >= ts[id_start+1][0]) & (event[:, 0] <= ts[id_end][1]), :].astype(np.long)
        #
        # event_vox0 = self.event2vox(event0.copy())
        # event_vox1 = self.event2vox(event1.copy())
        # event_vox2 = self.event2vox(event2.copy())
        # event_vox = torch.stack([event_vox0, event_vox1, event_vox2], dim=0)
        #
        # mask = []
        # for k in range(id_start-1, id_end+1):
        #     e1 = event[(event[:,0]>ts[k][0])&(event[:,0]<ts[k][1]), :]
        #     ecm = self.event2ecm(e1)
        #     m = (ecm!=0)
        #     mask.append(m)
        # mask0 = 1 - np.concatenate(mask[:-2], axis=0).astype(np.float)
        # mask1 = 1 - np.concatenate(mask[1:-1], axis=0).astype(np.float)
        # mask2 = 1 - np.concatenate(mask[2:], axis=0).astype(np.float)
        # mask = torch.stack([torch.from_numpy(mask0), torch.from_numpy(mask1), torch.from_numpy(mask2)], dim=0)
        # return event_vox, imgs, mask, gt, self.folder[idx]

    def __len__(self):
        return len(self.folder)

    def event2vox(self, event):
        event = torch.from_numpy(event).float()
        H, W = self.dim

        voxel_grid = torch.zeros(self.nb_of_bin, H, W, dtype=torch.float32, device='cpu')
        vox = voxel_grid.ravel()

        t, x, y, p = event.t()
        t = t.long()
        time_max = t.max()
        time_min = t.min()

        t = (t-time_min) * (self.nb_of_bin - 1) / (time_max-time_min)
        t = t.float()
        left_t, right_t = t.floor(), t.floor()+1
        left_x, right_x = x.float().floor(), x.float().floor()+1
        left_y, right_y = y.float().floor(), y.float().floor()+1

        for lim_x in [left_x, right_x]:
            for lim_y in [left_y, right_y]:
                for lim_t in [left_t, right_t]:
                    mask = (0 <= lim_x) & (0 <= lim_y) & (0 <= lim_t) & (lim_x <= W-1) & (lim_y <= H-1) & (lim_t <= self.nb_of_bin-1)
                    lin_idx = lim_x.long() + lim_y.long() * W + lim_t.long() * W * H
                    weight = p * (1-(lim_x-x).abs()) * (1-(lim_y-y).abs()) * (1-(lim_t-t).abs())
                    vox.index_add_(dim=0, index=lin_idx[mask], source=weight[mask].float())

        return voxel_grid

    def event2ecm(self, event):
        event = torch.from_numpy(event).float()
        H, W = self.dim

        voxel_grid = torch.zeros(1, H, W, dtype=torch.float32, device='cpu')
        vox = voxel_grid.ravel()

        t, x, y, p = event.t()
        left_x, right_x = x.float().floor(), x.float().floor()+1
        left_y, right_y = y.float().floor(), y.float().floor()+1

        for lim_x in [left_x, right_x]:
            for lim_y in [left_y, right_y]:
                    mask = (0 <= lim_x) & (0 <= lim_y) & (lim_x <= W-1) & (lim_y <= H-1)
                    lin_idx = lim_x.long() + lim_y.long() * W
                    weight = (1 - (lim_x - x).abs()) * (1 - (lim_y - y).abs())
                    vox.index_add_(dim=0, index=lin_idx[mask], source=weight[mask].float())

        return voxel_grid

    def visEvent(self, events, nb_of_bin, folder, format="%04d.jpg"):
        os.makedirs(folder, exist_ok=True)
        dt = (events[:, 0].max()-events[:, 0].min()) / nb_of_bin
        for k in range(nb_of_bin):
            e1 = events[(events[:, 0] >= k * dt) & (events[:, 0] <= (k + 1) * dt), :]
            ecm = np.zeros([260, 346, 3])
            for e in e1:
                if e[1] == 1:
                    ecm[int(e[3]), int(e[2]), 2] += 1
                else:
                    ecm[int(e[3]), int(e[2]), 0] += 1
            ecm[ecm > 0.8 * ecm.max()] = 0.8 * ecm.max()
            ecm /= ecm.max()
            ecm *= 255
            cv2.imwrite(os.path.join(folder, format % k), ecm)

    def event_grid(self, events):
        events = torch.from_numpy(events)

        t, x, y, p = events.t()
        if min(t.shape) == 0:
            print("Warning")

        t -= t.min()
        time_max = t.max()

        num_voxels = int(2 * np.prod(self.dim) * self.nb_of_bin)
        vox = events[0].new_full([num_voxels, ], fill_value=0)
        H, W = self.dim
        C = self.nb_of_bin

        # normalizing timestamps

        t = t * C/(time_max+1)
        t = t.long()

        # bin = 1 / C
        # s_bin = 0
        # e_bin = bin
        # for i in range(C):
        #     t[(s_bin <= t) == (t < e_bin)] = i
        #     s_bin += bin
        #     e_bin += bin
        # t[-1] = C - 1

        idx = x + W * y + W * H * t + W * H * C * p
        values = torch.full_like(t, 1)

        # draw in voxel grid
        vox.put_(idx.long(), values, accumulate=True)

        vox = vox.view(2, C, H, W)
        vox = torch.cat([vox[0, ...], vox[1, ...]], 0)
        # vox = vox.numpy()
        return vox

    def data_augmentation(self, e, i, m, gt, gt_x2, gt_x4, e01, e21, crop_size=(256, 256), train=True):
        n1 = random.randint(0, 3) if train else 2
        n2 = random.randint(0, 3) if train else 2
        flip1 = random.random() > 0.5 if train else False
        flip2 = random.random() > 0.5 if train else False

        e = e[:, :, n1:n1+crop_size[0], n2:n2+crop_size[1]]
        i = i[:, :, n1:n1+crop_size[0], n2:n2+crop_size[1]]
        m = m[:, :, n1:n1+crop_size[0], n2:n2+crop_size[1]]
        gt = gt[:, n1:n1+crop_size[0], n2:n2+crop_size[1]]
        gt_x2 = gt_x2[:, n1*2:n1*2+crop_size[0]*2, n2*2:n2*2+crop_size[1]*2]
        gt_x4 = gt_x4[:, n1*4:n1*4+crop_size[0]*4, n2*4:n2*4+crop_size[1]*4]
        e01 = e01[:, n1:n1+crop_size[0], n2:n2+crop_size[1]]
        e21 = e21[:, n1:n1+crop_size[0], n2:n2+crop_size[1]]

        e = e.reshape(-1, crop_size[0], crop_size[1]).transpose([1,2,0])
        i = i.reshape(-1, crop_size[0], crop_size[1]).transpose([1,2,0])
        m = m.reshape(-1, crop_size[0], crop_size[1]).transpose([1,2,0])
        gt = np.array(gt.permute(1,2,0))
        gt_x2 = np.array(gt_x2.permute(1,2,0))
        gt_x4 = np.array(gt_x4.permute(1,2,0))
        e01 = np.array(e01.permute(1,2,0))
        e21 = np.array(e21.permute(1,2,0))

        if flip1:
            e = cv2.flip(e, 0)
            i = cv2.flip(i, 0)
            m = cv2.flip(m, 0)
            gt = cv2.flip(gt, 0)
            gt_x2 = cv2.flip(gt_x2, 0)
            gt_x4 = cv2.flip(gt_x4, 0)
            e01 = cv2.flip(e01, 0)
            e21 = cv2.flip(e21, 0)
        if flip2:
            e = cv2.flip(e, 1)
            i = cv2.flip(i, 1)
            m = cv2.flip(m, 1)
            gt = cv2.flip(gt, 1)
            gt_x2 = cv2.flip(gt_x2, 1)
            gt_x4 = cv2.flip(gt_x4, 1)
            e01 = cv2.flip(e01, 1)
            e21 = cv2.flip(e21, 1)

        return e.transpose(2, 0, 1), i.transpose(2, 0, 1), m.transpose(2, 0, 1), gt.transpose(2, 0, 1), \
               gt_x2.transpose(2, 0, 1), gt_x4.transpose(2, 0, 1), e01.transpose(2, 0, 1), e21.transpose(2, 0, 1)


class EOccSR_dataset(data.Dataset):
    def __init__(self, args, train=True):
        if train:
            self.file = os.path.join(args.folder, 'train.txt')
        else:
            self.file = os.path.join(args.folder, 'test.txt')

        self.folder = []
        self.dim = (260, 260)
        self.nb_of_bin = 36

        with open(self.file, 'r') as f:
            for line in f.readlines():
                p1 = line.strip('\n')
                self.folder.append(os.path.join(args.folder, p1))

        self.train = train
        self.arg = args.arg

    def __getitem__(self, idx):
        event = np.load(os.path.join(self.folder[idx], 'events.npy'))
        mid = int(glob.glob(os.path.join(self.folder[idx], 'frame_*_1.jpg'))[0].split('_')[-2])
        ts = np.load(os.path.join(self.folder[idx], 'ts.npy'))
        frames = glob.glob(os.path.join(self.folder[idx], 'frame_*.jpg'))
        frames.sort()

        id_start = mid-8
        id_end = mid+9
        imgs = [transforms.ToTensor()(Image.open(i)) for i in frames]

        imgs_0 = torch.cat(imgs[id_start-1:id_end-1], dim=0)
        imgs_1 = torch.cat(imgs[id_start:id_end], dim=0)
        imgs_2 = torch.cat(imgs[id_start+1:id_end+1], dim=0)
        imgs = torch.stack([imgs_0, imgs_1, imgs_2], dim=0)

        event0 = event[(event[:, 0] >= ts[id_start-1][0]) & (event[:, 0] <= ts[id_end-2][1]), :].astype(np.int64)
        event1 = event[(event[:, 0] >= ts[id_start][0]) & (event[:, 0] <= ts[id_end-1][1]), :].astype(np.int64)
        event2 = event[(event[:, 0] >= ts[id_start+1][0]) & (event[:, 0] <= ts[id_end][1]), :].astype(np.int64)

        event_vox0 = self.event2vox(event0.copy())
        event_vox1 = self.event2vox(event1.copy())
        event_vox2 = self.event2vox(event2.copy())
        event_vox = torch.stack([event_vox0, event_vox1, event_vox2], dim=0)

        mask = []
        for k in range(id_start-1, id_end+1):
            e1 = event[(event[:,0]>ts[k][0])&(event[:,0]<ts[k][1]), :]
            ecm = self.event2ecm(e1)
            m = (ecm!=0)
            mask.append(m)
        mask0 = 1 - np.concatenate(mask[:-2], axis=0).astype(np.float32)
        mask1 = 1 - np.concatenate(mask[1:-1], axis=0).astype(np.float32)
        mask2 = 1 - np.concatenate(mask[2:], axis=0).astype(np.float32)
        mask = torch.stack([torch.from_numpy(mask0), torch.from_numpy(mask1), torch.from_numpy(mask2)], dim=0)

        gt_x4 = transforms.ToTensor()(Image.open(os.path.join(self.folder[idx], 'gt_kinect_x4_cvt.png')))

        data = np.load(os.path.join(self.folder[idx], 'data', 'flow.npy'))
        data = torch.from_numpy(data)
        event01 = data[9:9+5, ...]
        event21 = data[9+5:, ...]

        event_vox, imgs, mask, gt_x4, event01, event21 = self.data_augmentation(event_vox, imgs, mask, gt_x4, event01, event21, train=(self.train & self.arg))

        event_vox = event_vox.reshape([3, -1, 256, 256])
        imgs = imgs.reshape([3, -1, 256, 256])
        mask = mask.reshape([3, -1, 256, 256]).astype(np.float32)

        return event_vox, imgs, mask, gt_x4, event01, event21

    def __len__(self):
        return len(self.folder)

    def event2vox(self, event):
        event = torch.from_numpy(event).float()
        H, W = self.dim

        voxel_grid = torch.zeros(self.nb_of_bin, H, W, dtype=torch.float32, device='cpu')
        vox = voxel_grid.ravel()

        t, x, y, p = event.t()
        t = t.long()
        time_max = t.max()
        time_min = t.min()

        t = (t-time_min) * (self.nb_of_bin - 1) / (time_max-time_min)
        t = t.float()
        left_t, right_t = t.floor(), t.floor()+1
        left_x, right_x = x.float().floor(), x.float().floor()+1
        left_y, right_y = y.float().floor(), y.float().floor()+1

        for lim_x in [left_x, right_x]:
            for lim_y in [left_y, right_y]:
                for lim_t in [left_t, right_t]:
                    mask = (0 <= lim_x) & (0 <= lim_y) & (0 <= lim_t) & (lim_x <= W-1) & (lim_y <= H-1) & (lim_t <= self.nb_of_bin-1)
                    lin_idx = lim_x.long() + lim_y.long() * W + lim_t.long() * W * H
                    weight = p * (1-(lim_x-x).abs()) * (1-(lim_y-y).abs()) * (1-(lim_t-t).abs())
                    vox.index_add_(dim=0, index=lin_idx[mask], source=weight[mask].float())

        return voxel_grid

    def event2ecm(self, event):
        event = torch.from_numpy(event).float()
        H, W = self.dim

        voxel_grid = torch.zeros(1, H, W, dtype=torch.float32, device='cpu')
        vox = voxel_grid.ravel()

        t, x, y, p = event.t()
        left_x, right_x = x.float().floor(), x.float().floor()+1
        left_y, right_y = y.float().floor(), y.float().floor()+1

        for lim_x in [left_x, right_x]:
            for lim_y in [left_y, right_y]:
                    mask = (0 <= lim_x) & (0 <= lim_y) & (lim_x <= W-1) & (lim_y <= H-1)
                    lin_idx = lim_x.long() + lim_y.long() * W
                    weight = (1 - (lim_x - x).abs()) * (1 - (lim_y - y).abs())
                    vox.index_add_(dim=0, index=lin_idx[mask], source=weight[mask].float())

        return voxel_grid

    def data_augmentation(self, e, i, m, gt_x4, e01, e21, crop_size=(256, 256), train=True):
        n1 = random.randint(0, 3) if train else 2
        n2 = random.randint(0, 3) if train else 2
        flip1 = random.random() > 0.5 if train else False
        flip2 = random.random() > 0.5 if train else False

        e = e[:, :, n1:n1+crop_size[0], n2:n2+crop_size[1]]
        i = i[:, :, n1:n1+crop_size[0], n2:n2+crop_size[1]]
        m = m[:, :, n1:n1+crop_size[0], n2:n2+crop_size[1]]
        gt_x4 = gt_x4[:, n1*4:n1*4+crop_size[0]*4, n2*4:n2*4+crop_size[1]*4]
        e01 = e01[:, n1:n1+crop_size[0], n2:n2+crop_size[1]]
        e21 = e21[:, n1:n1+crop_size[0], n2:n2+crop_size[1]]

        e = np.array(e.reshape(-1, crop_size[0], crop_size[1]).permute([1,2,0]))
        i = np.array(i.reshape(-1, crop_size[0], crop_size[1]).permute([1,2,0]))
        m = np.array(m.reshape(-1, crop_size[0], crop_size[1]).permute([1,2,0]))
        gt_x4 = np.array(gt_x4.permute(1,2,0))
        e01 = np.array(e01.permute(1,2,0))
        e21 = np.array(e21.permute(1,2,0))

        if flip1:
            e = cv2.flip(e, 0)
            i = cv2.flip(i, 0)
            m = cv2.flip(m, 0)
            gt_x4 = cv2.flip(gt_x4, 0)
            e01 = cv2.flip(e01, 0)
            e21 = cv2.flip(e21, 0)
        if flip2:
            e = cv2.flip(e, 1)
            i = cv2.flip(i, 1)
            m = cv2.flip(m, 1)
            gt_x4 = cv2.flip(gt_x4, 1)
            e01 = cv2.flip(e01, 1)
            e21 = cv2.flip(e21, 1)

        return e.transpose(2, 0, 1), i.transpose(2, 0, 1), m.transpose(2, 0, 1), gt_x4.transpose(2, 0, 1), e01.transpose(2, 0, 1), e21.transpose(2, 0, 1)