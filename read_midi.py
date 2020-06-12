#!/usr/bin/env python
# -*- coding: utf8 -*-

from mido import MidiFile
from unidecode import unidecode
import numpy as np

#######
# Pianorolls dims are  :   TIME  *  PITCH


class Read_midi(object):
    def __init__(self, song_path, quantization):
        ## Metadata
        self.__song_path = song_path
        self.__quantization = quantization

        ## Pianoroll
        self.__T_pr = None

        ## Private misc
        self.__num_ticks = None
        self.__T_file = None

    @property
    def quantization(self):
        return self.__quantization

    @property
    def T_pr(self):
        return self.__T_pr

    @property
    def T_file(self):
        return self.__T_file

    def get_total_num_tick(self):
        # Midi length should be written in a meta message at the beginning of the file,
        # but in many cases, lazy motherfuckers didn't write it...

        # Read a midi file and return a dictionnary {track_name : pianoroll}
        mid = MidiFile(self.__song_path)

        # Parse track by track
        num_ticks = 0
        for i, track in enumerate(mid.tracks):
            tick_counter = 0
            for message in track:
                # Note on
                time = float(message.time)
                tick_counter += time
            num_ticks = max(num_ticks, tick_counter)
        self.__num_ticks = num_ticks

    def get_pitch_range(self):
        mid = MidiFile(self.__song_path)
        min_pitch = 200
        max_pitch = 0
        for i, track in enumerate(mid.tracks):
            for message in track:
                if message.type in ['note_on', 'note_off']:
                    pitch = message.note
                    if pitch > max_pitch:
                        max_pitch = pitch
                    if pitch < min_pitch:
                        min_pitch = pitch
        return min_pitch, max_pitch

    def get_time_file(self):
        # Get the time dimension for a pianoroll given a certain quantization
        mid = MidiFile(self.__song_path)
        # Tick per beat
        ticks_per_beat = mid.ticks_per_beat
        # Total number of ticks
        self.get_total_num_tick()
        # Dimensions of the pianoroll for each track
        self.__T_file = int((self.__num_ticks / ticks_per_beat) * self.__quantization)
        return self.__T_file

    def read_file(self):
        # Read the midi file and return a dictionnary {track_name : pianoroll}
        mid = MidiFile(self.__song_path)
        # Tick per beat
        ticks_per_beat = mid.ticks_per_beat

        # Get total time
        self.get_time_file()
        T_pr = self.__T_file
        # Pitch dimension
        N_pr = 128 # 128
        pianoroll = {}

        def add_note_to_pr(note_off, notes_on, pr):
            pitch_off, _, time_off = note_off
            # Note off : search for the note in the list of note on,
            # get the start and end time
            # write it in th pr
            match_list = [(ind, item) for (ind, item) in enumerate(notes_on) if item[0] == pitch_off]
            if len(match_list) == 0:
                print("Try to note off a note that has never been turned on")
                # Do nothing
                return

            # Add note to the pr
            pitch, velocity, time_on = match_list[0][1]
            pr[time_on:time_off, pitch] = velocity
            # Remove the note from notes_on
            ind_match = match_list[0][0]
            del notes_on[ind_match]
            return

        # Parse track by track
        counter_unnamed_track = 0
        for i, track in enumerate(mid.tracks):
            # Instanciate the pianoroll
            pr = np.zeros([T_pr, N_pr])
            time_counter = 0
            notes_on = []
            for message in track:

                ##########################################
                ##########################################
                ##########################################
                # TODO : keep track of tempo information
                # import re
                # if re.search("tempo", message.type):
                #     import pdb; pdb.set_trace()
                ##########################################
                ##########################################
                ##########################################


                # print message
                # Time. Must be incremented, whether it is a note on/off or not
                time = float(message.time)
                time_counter += time / ticks_per_beat * self.__quantization
                # Time in pr (mapping)
                time_pr = int(round(time_counter))
                # Note on
                if message.type == 'note_on':
                    # Get pitch
                    pitch = message.note
                    # Get velocity
                    velocity = message.velocity
                    if velocity > 0:
                        notes_on.append((pitch, velocity, time_pr))
                    elif velocity == 0:
                        add_note_to_pr((pitch, velocity, time_pr), notes_on, pr)
                # Note off
                elif message.type == 'note_off':
                    pitch = message.note
                    velocity = message.velocity
                    add_note_to_pr((pitch, velocity, time_pr), notes_on, pr)

            # We deal with discrete values ranged between 0 and 127
            #     -> convert to int
            pr = pr.astype(np.int16)
            if np.sum(np.sum(pr)) > 0:
                name = unidecode(track.name)
                name = name.rstrip('\x00')
                if name == u'':
                    name = 'unnamed' + str(counter_unnamed_track)
                    counter_unnamed_track += 1
                if name in pianoroll.keys():
                    # Take max of the to pianorolls
                    pianoroll[name] = np.maximum(pr, pianoroll[name])
                else:
                    pianoroll[name] = pr
        return pianoroll

import os
import utils

if __name__ == '__main__':
    # filepath = "/Users/seokin/Workspace/midi_to_numpy/datasets/classic/Beethoven/Overture ''Fidelio'' op72b.mid"
    dirpath = "/Users/seokin/Workspace/midi_to_numpy/datasets/classic/Beethoven"
    filepaths = []
    output_data = []
    start_seq_len = 32
    max_seq_len = 64

    i = 0
    for filename in os.listdir(dirpath):
        if  '.mid' in filename:
            filepath = dirpath + '/' + filename
            filepaths.append(filepath)
            # with open(os.path.join(os.cwd(), filename), 'r') as f:     
            aaa = Read_midi(filepath, 16).read_file()

            # TODO 1 : (, 128) -> (, 88)
            bbb = utils.dict_to_matrix(aaa)
            total_seq_len = len(bbb)
            cur_seq_pos = start_seq_len

            while cur_seq_pos < total_seq_len:
                bbb_fixed = bbb[cur_seq_pos:, 20:][:max_seq_len, :-20]
                
                if len(bbb_fixed) < max_seq_len:
                    break

                if bbb_fixed.max() != 0:                
                    # output_data[filename] = bbb_fixed.copy()
                    output_data.append(bbb_fixed.copy())
                    print("- %04d Load (%d,%d) from file : %s"%(i+1, bbb_fixed.shape[0], bbb_fixed.shape[1], filename))
                    i += 1

                cur_seq_pos = cur_seq_pos + max_seq_len
        
    idxs = np.arange(len(output_data))
    train_idxs = np.random.choice(idxs, size=int(len(output_data)*0.9), replace=False)
    test_idxs = np.delete(idxs, train_idxs)

    np.save('beethoven64_train.npy', np.array(output_data)[train_idxs])
    np.save('beethoven64_test.npy', np.array(output_data)[test_idxs])

    # output : {"songname": np.matrix(max_seq_len, note)}
