import torch
import numpy as np
from scipy import sparse

def get_local_map(positions):#batch_size*maxlen
    try:
        position_list=list(list(map(int,i)) for i in positions)
    except:
        print(positions)
        position_list=[[0]*len(positions[0]) for _ in range(len(positions))]
    maps = torch.ones(len(position_list),len(position_list[0]),len(position_list[0]))
    for i in range(len(position_list)):
        start=-1
        end=-1
        for j in range(len(position_list[0])):
            maps[i,j,j]=0
            if position_list[i][j]==1 and start==-1:
                start=j
            if start>=0 and position_list[i][j]==0:
                end=j
                maps[i,start:end,start:end]=0
                start=-1
                end=-1
    return maps

def get_simple_controlflow_from_instatement(instatements):
    cfg = torch.zeros(len(instatements),len(instatements[0]),len(instatements[0]))
    for j in range(len(instatements)):
        instatement = instatements[j]
        start = -1
        end = -1
        last_start = -1
        last_end = -1
        for i in range(len(instatement)):
            if start >= 0 and instatement[i] == 0:
                end = i
                if last_start != -1:
                    cfg[j, start:end, last_start:last_end] = 1
                last_start = start
                last_end = end
                start = -1
                end = -1
            elif start == -1 and instatement[i] == 1:
                start = i
    return cfg

def get_intoken_map(positions):#batch_size*maxlen
    try:
        position_list=list(list(map(int,i)) for i in positions)
    except:
        print(positions)
        position_list=[[0]*len(positions[0]) for _ in range(len(positions))]
    maps = torch.ones(len(position_list),len(position_list[0]),len(position_list[0]))
    for i in range(len(position_list)):
        start=-1
        end=-1
        for j in range(len(position_list[0])):
            maps[i,j,j]=0
            if position_list[i][j] != 0 and start == -1:
                start = j
            if start >= 0 and position_list[i][j] != position_list[i][start]:
                end=j
                maps[i,start:end,start:end]=0
                if position_list[i][j] != 0:
                    start = j
                else:
                    start=-1
                    end=-1
    return maps

def get_instatement_map(positions):#batch_size*maxlen
    try:
        position_list=list(list(map(int,i)) for i in positions)
    except:
        print(positions)
        position_list=[[0]*len(positions[0]) for _ in range(len(positions))]
    maps = torch.ones(len(position_list),len(position_list[0]),len(position_list[0]))
    for i in range(len(position_list)):
        start=0
        end=0
        for j in range(len(position_list[0])):
            maps[i,j,j]=0
            if position_list[i][j] != position_list[i][start]:
                end=j
                maps[i,start:end,start:end]=0
                start=j
                end=j
    return maps

def vectorize(ex, model):
    """Vectorize a single example."""
    src_dict = model.src_dict
    tgt_dict = model.tgt_dict

    code, summary = ex['code'], ex['summary']
    vectorized_ex = dict()
    vectorized_ex['id'] = code.id
    vectorized_ex['language'] = code.language

    vectorized_ex['code'] = code.text
    vectorized_ex['code_tokens'] = code.tokens
    vectorized_ex['code_subtokens'] = code.subtoken
    vectorized_ex['code_char_rep'] = None
    vectorized_ex['code_type_rep'] = None
    vectorized_ex['code_mask_rep'] = None
    vectorized_ex['code_keyword'] = list(map(int,code.keyword))
    vectorized_ex['code_intoken'] = list(map(int,code.intoken))
    vectorized_ex['code_instatement'] = list(map(int,code.instatement))
    # sparse matrix
    vectorized_ex['code_dataflow'] = code.dataflow
    vectorized_ex['code_controlflow'] = code.controlflow
    vectorized_ex['use_code_mask'] = False

    vectorized_ex['code_word_rep'] = torch.LongTensor(code.vectorize(word_dict=src_dict))
    if model.args.use_src_char:
        vectorized_ex['code_char_rep'] = torch.LongTensor(code.vectorize(word_dict=src_dict, _type='char'))
    if model.args.use_code_type:
        vectorized_ex['code_type_rep'] = torch.LongTensor(code.type)
    if code.mask:
        vectorized_ex['code_mask_rep'] = torch.LongTensor(code.mask)
        vectorized_ex['use_code_mask'] = True

    vectorized_ex['summ'] = None
    vectorized_ex['summ_tokens'] = None
    vectorized_ex['stype'] = None
    vectorized_ex['summ_word_rep'] = None
    vectorized_ex['summ_char_rep'] = None
    vectorized_ex['target'] = None

    if summary is not None:
        vectorized_ex['summ'] = summary.text
        vectorized_ex['summ_tokens'] = summary.tokens
        vectorized_ex['stype'] = summary.type
        vectorized_ex['summ_word_rep'] = torch.LongTensor(summary.vectorize(word_dict=tgt_dict))
        if model.args.use_tgt_char:
            vectorized_ex['summ_char_rep'] = torch.LongTensor(summary.vectorize(word_dict=tgt_dict, _type='char'))
        # target is only used to compute loss during training
        vectorized_ex['target'] = torch.LongTensor(summary.vectorize(tgt_dict))

    vectorized_ex['src_vocab'] = code.src_vocab
    vectorized_ex['use_src_word'] = model.args.use_src_word
    vectorized_ex['use_tgt_word'] = model.args.use_tgt_word
    vectorized_ex['use_src_char'] = model.args.use_src_char
    vectorized_ex['use_tgt_char'] = model.args.use_tgt_char
    vectorized_ex['use_code_type'] = model.args.use_code_type

    return vectorized_ex


def batchify(batch):
    """Gather a batch of individual examples into one batch."""

    # batch is a list of vectorized examples
    batch_size = len(batch)
    use_src_word = batch[0]['use_src_word']
    use_tgt_word = batch[0]['use_tgt_word']
    use_src_char = batch[0]['use_src_char']
    use_tgt_char = batch[0]['use_tgt_char']
    use_code_type = batch[0]['use_code_type']
    use_code_mask = batch[0]['use_code_mask']
    ids = [ex['id'] for ex in batch]
    language = [ex['language'] for ex in batch]

    # --------- Prepare Code tensors ---------
    code_words = [ex['code_word_rep'] for ex in batch]
    code_chars = [ex['code_char_rep'] for ex in batch]
    code_type = [ex['code_type_rep'] for ex in batch]
    code_mask = [ex['code_mask_rep'] for ex in batch]
    max_code_len = max([d.size(0) for d in code_words])
    code_keyword = [ex['code_keyword']+['0' for _ in range(max_code_len-len(ex['code_keyword']))] for ex in batch]
    code_intoken = [ex['code_intoken']+['0' for _ in range(max_code_len-len(ex['code_intoken']))] for ex in batch]
    code_instatement = [ex['code_instatement']+['0' for _ in range(max_code_len-len(ex['code_instatement']))] for ex in batch]
    code_dataflow = np.array([ex['code_dataflow'].toarray() for ex in batch])
    code_controlflow = np.array([ex['code_controlflow'].toarray() for ex in batch])
    if use_src_char:
        max_char_in_code_token = code_chars[0].size(1)

    # Batch Code Representations
    code_len_rep = torch.zeros(batch_size, dtype=torch.long)
    code_word_rep = torch.zeros(batch_size, max_code_len, dtype=torch.long) \
        if use_src_word else None
    code_type_rep = torch.zeros(batch_size, max_code_len, dtype=torch.long) \
        if use_code_type else None
    code_mask_rep = torch.zeros(batch_size, max_code_len, dtype=torch.long) \
        if use_code_mask else None
    code_char_rep = torch.zeros(batch_size, max_code_len, max_char_in_code_token, dtype=torch.long) \
        if use_src_char else None
    # code_keyword_rep = torch.zeros(batch_size, max_code_len, dtype=torch.long)
    # code_intoken_rep = torch.zeros(batch_size, max_code_len, dtype=torch.long)
    # code_instatement_rep = torch.zeros(batch_size, max_code_len, dtype=torch.long)

    code_keyword_rep = torch.Tensor(list(list(map(int,i)) for i in code_keyword))
    code_intoken_map = get_intoken_map(code_intoken)
    code_instatement_map = get_instatement_map(code_instatement)
    #print(type(code_dataflow))
    code_dataflow_map = torch.from_numpy(code_dataflow)
    #code_controlflow_map = torch.from_numpy(code_controlflow)
    code_controlflow_map = code_dataflow_map
    # code_controlflow_map = get_simple_controlflow_from_instatement(code_instatement)

    source_maps = []
    src_vocabs = []
    # code_words是一个batch_size*max_code_len*dim的向量，这里是把他装进batch的code_word_rep�?
    # code_word_rep在上面创建时是二维的，后面变成三维的了？不是三维，前一步查表只查了数，还没变成tensor
    for i in range(batch_size):
        code_len_rep[i] = code_words[i].size(0)
        if use_src_word:
            code_word_rep[i, :code_words[i].size(0)].copy_(code_words[i])
        if use_code_type:
            code_type_rep[i, :code_type[i].size(0)].copy_(code_type[i])
        if use_code_mask:
            code_mask_rep[i, :code_mask[i].size(0)].copy_(code_mask[i])
        if use_src_char:
            code_char_rep[i, :len(code_chars[i]), :].copy_(code_chars[i])
        #code_keyword_rep[i, :len(code_keyword[i])].copy_(torch.Tensor(code_keyword[i]))
        #code_intoken_rep[i, :len(code_intoken[i])].copy_(torch.Tensor(code_intoken[i]))
        #code_instatement_rep[i, :len(code_instatement[i])].copy_(torch.Tensor(code_instatement[i]))
        #
        context = batch[i]['code_tokens']
        vocab = batch[i]['src_vocab']
        src_vocabs.append(vocab)
        # Mapping source tokens to indices in the dynamic dict.
        src_map = torch.LongTensor([vocab[w] for w in context])
        source_maps.append(src_map)

    # --------- Prepare Summary tensors ---------
    no_summary = batch[0]['summ_word_rep'] is None
    if no_summary:
        summ_len_rep = None
        summ_word_rep = None
        summ_char_rep = None
        tgt_tensor = None
        alignments = None
    else:
        summ_words = [ex['summ_word_rep'] for ex in batch]
        summ_chars = [ex['summ_char_rep'] for ex in batch]
        max_sum_len = max([q.size(0) for q in summ_words])
        if use_tgt_char:
            max_char_in_summ_token = summ_chars[0].size(1)

        summ_len_rep = torch.zeros(batch_size, dtype=torch.long)
        summ_word_rep = torch.zeros(batch_size, max_sum_len, dtype=torch.long) \
            if use_tgt_word else None
        summ_char_rep = torch.zeros(batch_size, max_sum_len, max_char_in_summ_token, dtype=torch.long) \
            if use_tgt_char else None

        max_tgt_length = max([ex['target'].size(0) for ex in batch])
        tgt_tensor = torch.zeros(batch_size, max_tgt_length, dtype=torch.long)
        alignments = []
        for i in range(batch_size):
            summ_len_rep[i] = summ_words[i].size(0)
            if use_tgt_word:
                summ_word_rep[i, :summ_words[i].size(0)].copy_(summ_words[i])
            if use_tgt_char:
                summ_char_rep[i, :summ_chars[i].size(0), :].copy_(summ_chars[i])
            #
            tgt_len = batch[i]['target'].size(0)
            tgt_tensor[i, :tgt_len].copy_(batch[i]['target'])
            target = batch[i]['summ_tokens']
            align_mask = torch.LongTensor([src_vocabs[i][w] for w in target])
            alignments.append(align_mask)

    return {
        'ids': ids,
        'language': language,
        'batch_size': batch_size,
        'code_word_rep': code_word_rep,
        'code_char_rep': code_char_rep,
        'code_type_rep': code_type_rep,
        'code_mask_rep': code_mask_rep,
        'code_keyword': code_keyword_rep,
        'code_intoken': code_intoken_map,
        'code_instatement': code_instatement_map,
        'code_dataflow': code_dataflow_map,
        'code_controlflow': code_controlflow_map,
        'code_len': code_len_rep,
        'summ_word_rep': summ_word_rep,
        'summ_char_rep': summ_char_rep,
        'summ_len': summ_len_rep,
        'tgt_seq': tgt_tensor,
        'code_text': [ex['code'] for ex in batch],
        'code_tokens': [ex['code_tokens'] for ex in batch],
        'summ_text': [ex['summ'] for ex in batch],
        'summ_tokens': [ex['summ_tokens'] for ex in batch],
        'src_vocab': src_vocabs,
        'src_map': source_maps,
        'alignment': alignments,
        'stype': [ex['stype'] for ex in batch]
    }